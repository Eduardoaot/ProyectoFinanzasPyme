"""Proyecciones y consejos: ventas, utilidad, efectivo día por día, equilibrio, inventario y ahorro.

`cargar_insumos` lee la base de datos una sola vez; `calcular` es una función pura (mismas entradas →
mismas salidas) que también atiende los escenarios "¿qué pasa si…?" sin volver a consultar nada.
"""

import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import Connection, text

from app.alerts.reglas import Alerta
from app.deudas import consultas as dq
from app.deudas import formulas as df
from app.finance import consultas as q
from app.finance import servicio as fin
from app.finance.formato import dinero, numero, pct
from app.finance.periodos import MESES, fin_de_mes, sumar_meses
from app.forecasting.servicio import completar_dias
from app.impuestos import servicio as imp
from app.proyecciones import formulas as pf
from app.proyecciones.pronostico import Z_80, pronosticar

HORIZONTE_INTERNO = 92
LEAD_TIME_DEFECTO = 3
PERIODO_REVISION = 7
PCT_EXTRA_DEUDA = 0.20          # de lo que queda tras impuestos y pagos obligatorios, si hay deuda con tasa > 30 %
TASA_DEUDA_CARA = 0.30
PCT_REINVERSION = 0.25          # del remanente después del fondo de emergencia
DIAS_MINIMO_SEGURIDAD = 15


@dataclass
class ProductoIn:
    id: int
    nombre: str
    unidad: str
    stock: float
    costo: float
    precio: float
    lead_time: int
    empaque: float
    unidades: list[float]             # unidades vendidas por día, últimos 28 días (más antiguo primero)


@dataclass
class Insumos:
    corte: date
    ventas: list[tuple[date, float]]
    margen_bruto: float
    gastos_fijos_mensual: float
    gastos_var_pct: float
    gastos_op_mensual: float
    calendario_fijos: list[tuple[int, float]]
    efectivo: float
    minimo_seguridad: float
    fondo_emergencia: float
    productos: list[ProductoIn]
    pagos_deuda: list[tuple[date, float, str]]
    pago_deuda_mensual: float
    hay_deuda_cara: bool
    tasa_impuesto: float
    impuesto_pendiente: tuple[date, float] | None
    dia_impuesto: int
    gasto_diario: float
    ventas_mensuales_previas: list[float] = field(default_factory=list)


@dataclass
class Escenario:
    ventas_pct: float = 0.0               # -0.30 … +0.30
    precios_pct: float = 0.0              # -0.10 … +0.10
    gasto_fijo_extra: float = 0.0         # nuevo gasto fijo mensual
    deuda_monto: float = 0.0
    deuda_tasa: float = 0.0               # anual (fracción)
    deuda_plazo: int = 0                  # meses


def r2(v: float) -> float:
    return round(v + 0.0, 2)


# ----------------------------------------------------------------------------- carga


def cargar_insumos(conn: Connection, id_empresa: int) -> Insumos | None:
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return None
    emp = q.empresa(conn, id_empresa)
    hist_desde = corte - timedelta(days=167)
    ventas = [(pt.fecha, pt.valor) for pt in completar_dias(
        [(r["fecha"], r["ingreso"]) for r in q.ventas_diarias(conn, id_empresa, hist_desde, corte)], hist_desde, corte)]
    # Ventana de ~3 meses: si el corte es fin de mes, los 3 meses calendario completos (p. ej. jul-sep); si no, 90 días.
    if corte == fin_de_mes(corte):
        d90, meses_v = sumar_meses(corte.replace(day=1), -2), 3.0
    else:
        d90, meses_v = corte - timedelta(days=89), 90 / 30.4375
    dias_v = (corte - d90).days + 1
    v90 = q.ventas_diarias(conn, id_empresa, d90, corte)
    ventas_90 = float(sum(r["ingreso"] for r in v90))
    costo_90 = float(sum(r["costo"] for r in v90))
    margen = (ventas_90 - costo_90) / ventas_90 if ventas_90 > 0 else 0.0
    gastos = q.gastos_diarios(conn, id_empresa, d90, corte)
    fijo_90 = float(sum(g["monto"] for g in gastos if g["tipo"] == "fijo"))
    var_90 = float(sum(g["monto"] for g in gastos if g["tipo"] == "variable"))
    compras_90 = float(sum(c["monto"] for c in q.compras_diarias(conn, id_empresa, d90, corte)))

    fijos_rows = conn.execute(text(
        "SELECT concepto, fecha, monto FROM gastos_operativos WHERE id_empresa = :e AND tipo = 'fijo' AND fecha >= :d AND fecha <= :h"),
        {"e": id_empresa, "d": d90.isoformat(), "h": corte.isoformat()}).mappings().all()
    por_concepto: dict[str, dict] = {}
    for r in fijos_rows:
        c = por_concepto.setdefault(r["concepto"], {"total": 0.0, "ultima": date.min})
        c["total"] += float(r["monto"])
        c["ultima"] = max(c["ultima"], q.a_fecha(r["fecha"]))
    calendario = [(c["ultima"].day, c["total"] / meses_v) for c in por_concepto.values()]

    # Productos y unidades vendidas por día (últimos 28 días).
    d28 = corte - timedelta(days=27)
    unidades: dict[int, dict[date, float]] = defaultdict(dict)
    for r in conn.execute(text(
            "SELECT id_producto, fecha, unidades FROM v_ventas_diarias WHERE id_empresa = :e AND fecha >= :d AND fecha <= :h"),
            {"e": id_empresa, "d": d28.isoformat(), "h": corte.isoformat()}).mappings():
        unidades[r["id_producto"]][q.a_fecha(r["fecha"])] = float(r["unidades"])
    extras = {r["id_producto"]: r for r in conn.execute(text(
        "SELECT id_producto, lead_time_dias, empaque FROM productos_cat WHERE id_empresa = :e"), {"e": id_empresa}).mappings()}
    productos = []
    for p in q.productos(conn, id_empresa):
        ex = extras.get(p["id_producto"], {})
        serie = [unidades[p["id_producto"]].get(d28 + timedelta(days=i), 0.0) for i in range(28)]
        productos.append(ProductoIn(
            p["id_producto"], p["sku_o_nombre"], p["unidad"], float(p["stock_actual"]), float(p["costo_promedio"]),
            float(p["precio_venta"]), int(ex.get("lead_time_dias") or LEAD_TIME_DEFECTO),
            float(ex.get("empaque") or 1), serie))

    pagos_d = dq.pagos_programados(conn, id_empresa, corte, meses=4)
    activas = dq.listar(conn, id_empresa, incluir_liquidadas=False)
    sims = [dq.a_sim(d, corte) for d in activas]
    pago_mensual = sum(df.pago_programado(s, s.saldo) + s.comision for s in sims)
    hay_cara = any(float(d["tasa_interes_anual"]) > TASA_DEUDA_CARA for d in activas)

    fiscal = imp.resumen_para_proyeccion(conn, id_empresa)
    pendiente = (fiscal["pendiente"]["fecha"], fiscal["pendiente"]["monto"]) if fiscal.get("pendiente") else None

    gastos_op_mensual = (fijo_90 + var_90) / meses_v
    minimo = float(emp["minimo_seguridad"]) if emp.get("minimo_seguridad") is not None else (fijo_90 / meses_v) / 30 * DIAS_MINIMO_SEGURIDAD
    previas = []
    primer_mes = (corte + timedelta(days=1)).replace(day=1)
    acum: dict[tuple[int, int], float] = defaultdict(float)
    for fe, v in ventas:
        if fe < primer_mes:
            acum[(fe.year, fe.month)] += v
    previas = [acum[k] for k in sorted(acum)[-3:] if _mes_completo(ventas, k)]

    return Insumos(
        corte=corte, ventas=ventas, margen_bruto=margen, gastos_fijos_mensual=fijo_90 / meses_v,
        gastos_var_pct=var_90 / ventas_90 if ventas_90 > 0 else 0.0, gastos_op_mensual=gastos_op_mensual,
        calendario_fijos=calendario, efectivo=float(fin.flujo_saldo(conn, id_empresa, corte)), minimo_seguridad=minimo,
        fondo_emergencia=float(conn.execute(text("SELECT fondo_emergencia FROM empresas WHERE id_empresa = :e"), {"e": id_empresa}).scalar() or 0),
        productos=productos, pagos_deuda=pagos_d, pago_deuda_mensual=pago_mensual, hay_deuda_cara=hay_cara,
        tasa_impuesto=fiscal["tasa_efectiva"], impuesto_pendiente=pendiente, dia_impuesto=fiscal.get("dia_pago", 17),
        gasto_diario=(fijo_90 + var_90 + compras_90) / dias_v, ventas_mensuales_previas=previas,
    )


def _mes_completo(ventas: list[tuple[date, float]], clave: tuple[int, int]) -> bool:
    dias = {fe for fe, _ in ventas if (fe.year, fe.month) == clave}
    return len(dias) == calendar.monthrange(*clave)[1]


# ----------------------------------------------------------------------------- cálculo


def _etiqueta_mes(d: date) -> str:
    return f"{MESES[d.month - 1].capitalize()} {d.year}"


def calcular(ins: Insumos, esc: Escenario | None = None, semanas: int = 8) -> dict:
    esc = esc or Escenario()
    corte = ins.corte
    fv, fp = 1 + esc.ventas_pct, 1 + esc.precios_pct
    pron = pronosticar(ins.ventas, HORIZONTE_INTERNO)
    sigma = pron.sigma_diaria * fv * fp
    margen_ref = 1 - (1 - ins.margen_bruto) / fp         # margen bruto con el nuevo precio (el costo no sube)
    venta_dia: dict[date, float] = {}
    costo_dia: dict[date, float] = {}
    for fe, v in zip(pron.fechas, pron.valores):
        venta_dia[fe] = v * fv * fp
        costo_dia[fe] = v * fv * (1 - ins.margen_bruto)
    real = {fe: v for fe, v in ins.ventas}

    # ---- mes de referencia (el mes en el que cae el primer día pronosticado)
    inicio_mes = (corte + timedelta(days=1)).replace(day=1)
    fin_mes = fin_de_mes(inicio_mes)
    dias_mes = [inicio_mes + timedelta(days=i) for i in range((fin_mes - inicio_mes).days + 1)]
    real_mes = sum(real.get(d, 0.0) for d in dias_mes if d <= corte)
    fc_dias = [d for d in dias_mes if d > corte]
    ventas_mes = real_mes + sum(venta_dia[d] for d in fc_dias)
    costo_mes = (real_mes / 1.0) * (1 - ins.margen_bruto) + sum(costo_dia[d] for d in fc_dias)
    var_mes = ins.gastos_var_pct * ventas_mes
    fijos_mes = ins.gastos_fijos_mensual + esc.gasto_fijo_extra
    utilidad_mes = ventas_mes - costo_mes - fijos_mes - var_mes
    ancho_ventas = Z_80 * sigma * len(fc_dias) ** 0.5
    efecto_utilidad = ancho_ventas * max(0.0, (1 - costo_mes / ventas_mes if ventas_mes else 0) - ins.gastos_var_pct)
    mes = {
        "etiqueta": _etiqueta_mes(inicio_mes), "desde": inicio_mes.isoformat(), "hasta": fin_mes.isoformat(),
        "ventas_reales_a_la_fecha": r2(real_mes), "ventas": r2(ventas_mes),
        "ventas_pesimista": r2(max(real_mes, ventas_mes - ancho_ventas)), "ventas_optimista": r2(ventas_mes + ancho_ventas),
        "costo": r2(costo_mes), "gastos_fijos": r2(fijos_mes), "gastos_variables": r2(var_mes),
        "utilidad": r2(utilidad_mes), "utilidad_pesimista": r2(utilidad_mes - efecto_utilidad), "utilidad_optimista": r2(utilidad_mes + efecto_utilidad),
        "margen_bruto": margen_ref,
    }

    # ---- gráfica semanal: 12 semanas reales + semanas pronosticadas con su banda
    semanas_series = []
    bloques = [ins.ventas[len(ins.ventas) - 7 * (k + 1): len(ins.ventas) - 7 * k] for k in range(11, -1, -1) if len(ins.ventas) >= 7 * (k + 1)]
    for b in bloques:
        semanas_series.append({"fecha": b[0][0].isoformat(), "real": r2(sum(v for _, v in b)), "pronostico": None, "pesimista": None, "optimista": None})
    for w in range(semanas):
        idx = range(7 * w, 7 * w + 7)
        fechas = [pron.fechas[i] for i in idx]
        total = sum(venta_dia[d] for d in fechas)
        ancho = Z_80 * sigma * 7 ** 0.5
        semanas_series.append({"fecha": fechas[0].isoformat(), "real": None, "pronostico": r2(total),
                               "pesimista": r2(max(0.0, total - ancho)), "optimista": r2(total + ancho)})
    if bloques and semanas_series:     # une la línea real con la punteada
        ultimo_real = len(bloques) - 1
        semanas_series[ultimo_real]["pronostico"] = semanas_series[ultimo_real]["real"]
        semanas_series[ultimo_real]["pesimista"] = semanas_series[ultimo_real]["optimista"] = semanas_series[ultimo_real]["real"]
    total_horizonte = sum(venta_dia[corte + timedelta(days=i)] for i in range(1, 7 * semanas + 1))

    # ---- flujo de efectivo diario
    pagos_deuda = list(ins.pagos_deuda)
    if esc.deuda_monto > 0 and esc.deuda_plazo > 0:
        cuota = df.pago_fijo(esc.deuda_monto, esc.deuda_tasa, esc.deuda_plazo)
        for k in range(1, 4):
            m_ = (corte.replace(day=1) + timedelta(days=32 * k)).replace(day=1)
            pagos_deuda.append((m_, cuota, "Nueva deuda"))
    pago_deuda_mensual = ins.pago_deuda_mensual + (df.pago_fijo(esc.deuda_monto, esc.deuda_tasa, esc.deuda_plazo)
                                                   if esc.deuda_monto > 0 and esc.deuda_plazo > 0 else 0.0)
    pagos_dia: dict[date, list[tuple[float, str]]] = defaultdict(list)
    for fe, monto, quien in pagos_deuda:
        pagos_dia[fe].append((monto, f"el pago a {quien}"))

    def ventas_del_mes(anio: int, mes_: int) -> float:
        total = 0.0
        for dia in range(1, calendar.monthrange(anio, mes_)[1] + 1):
            d = date(anio, mes_, dia)
            total += real[d] if d in real and d <= corte else venta_dia.get(d, 0.0)
        return total

    saldo = ins.efectivo + (esc.deuda_monto if esc.deuda_monto > 0 and esc.deuda_plazo > 0 else 0.0)
    flujo, fecha_riesgo, causa_riesgo = [], None, None
    margen_caja = max(0.0, ins.margen_bruto - ins.gastos_var_pct)
    for i, d in enumerate(pron.fechas, start=1):
        salidas: list[tuple[float, str]] = []
        fijo_dia = sum(m_ for dia, m_ in ins.calendario_fijos if min(dia, calendar.monthrange(d.year, d.month)[1]) == d.day)
        if d.day == 1:
            fijo_dia += esc.gasto_fijo_extra
        if fijo_dia:
            salidas.append((fijo_dia, "los gastos fijos"))
        salidas.extend(pagos_dia.get(d, []))
        if d.day == ins.dia_impuesto:
            if ins.impuesto_pendiente and ins.impuesto_pendiente[0] == d:
                imp_dia = ins.impuesto_pendiente[1]
            else:
                ant = d.replace(day=1) - timedelta(days=1)
                imp_dia = ins.tasa_impuesto * ventas_del_mes(ant.year, ant.month)
            if imp_dia > 0:
                salidas.append((imp_dia, "los impuestos"))
        neto = venta_dia[d] - costo_dia[d] - ins.gastos_var_pct * venta_dia[d] - sum(m_ for m_, _ in salidas)
        saldo += neto
        ancho = Z_80 * sigma * i ** 0.5 * margen_caja
        pes = saldo - ancho
        flujo.append({"fecha": d.isoformat(), "esperado": r2(saldo), "pesimista": r2(pes), "optimista": r2(saldo + ancho)})
        if fecha_riesgo is None and pes < ins.minimo_seguridad:
            fecha_riesgo = d
            mayor = max(salidas, default=(0.0, "las ventas más bajas de lo normal"), key=lambda s: s[0])
            causa_riesgo = {"monto": r2(mayor[0]), "concepto": mayor[1]}
    por_fecha = {p["fecha"]: p for p in flujo}
    fin_mes_p = por_fecha.get(fin_mes.isoformat(), flujo[-1])
    colchon = pf.dias_de_colchon(ins.efectivo, ins.gasto_diario + pago_deuda_mensual / 30)
    flujo_out = {
        "efectivo_actual": r2(ins.efectivo), "minimo_seguridad": r2(ins.minimo_seguridad), "serie": flujo[:HORIZONTE_INTERNO],
        "fin_de_mes": {"fecha": fin_mes.isoformat(), "esperado": fin_mes_p["esperado"], "pesimista": fin_mes_p["pesimista"], "optimista": fin_mes_p["optimista"]},
        "dias_colchon": None if colchon is None else round(colchon, 1),
        "fecha_riesgo": fecha_riesgo.isoformat() if fecha_riesgo else None, "causa_riesgo": causa_riesgo,
    }

    # ---- punto de equilibrio
    gastos_op = ins.gastos_op_mensual + esc.gasto_fijo_extra
    pe = pf.punto_equilibrio_mensual(gastos_op, margen_ref)
    acumulado, cubierto = 0.0, None
    for d in dias_mes:
        v = real.get(d, 0.0) if d <= corte else venta_dia.get(d, 0.0)
        acumulado += v * margen_ref
        if cubierto is None and acumulado >= gastos_op:
            cubierto = d
    equilibrio = {
        "mensual": None if pe is None else r2(pe), "diario": None if pe is None else r2(pe / len(dias_mes)),
        "gastos_operacion_mensuales": r2(gastos_op), "margen_bruto": margen_ref,
        "margen_seguridad": pf.margen_de_seguridad(ventas_mes, pe),
        "dia_cubierto": cubierto.isoformat() if cubierto else None,
        "faltante": r2(max(0.0, gastos_op - acumulado)) if cubierto is None else 0.0,
        "avance": min(1.0, acumulado / gastos_op) if gastos_op > 0 else 1.0, "ventas_proyectadas": r2(ventas_mes),
    }

    # ---- inventario
    inventario = _inventario(ins, pron, ins.efectivo, margen_ref, fp, real, corte)

    # ---- consejos
    impuesto_mes = ins.tasa_impuesto * ventas_mes
    extra_deuda_deseado = 0.0
    obligatorio = impuesto_mes + pago_deuda_mensual
    if ins.hay_deuda_cara and utilidad_mes > obligatorio:
        extra_deuda_deseado = PCT_EXTRA_DEUDA * (utilidad_mes - obligatorio)
    meta_fondo = pf.meta_fondo_emergencia(fijos_mes, pago_deuda_mensual)
    ahorro_sugerido = max(0.0, (meta_fondo - ins.fondo_emergencia) / 6)
    restante_tras_fondo = max(0.0, utilidad_mes - obligatorio - extra_deuda_deseado - ahorro_sugerido)
    reserva_inventario = sum(p["costo_compra"] for p in inventario["productos"])
    reparto = pf.distribuir_utilidad(utilidad_mes, impuesto_mes, pago_deuda_mensual, extra_deuda_deseado, ahorro_sugerido,
                                     PCT_REINVERSION * restante_tras_fondo)
    consejos = {
        "apartado_impuestos": r2(impuesto_mes),
        "fondo_emergencia": {"meta": r2(meta_fondo), "actual": r2(ins.fondo_emergencia),
                             "avance": min(1.0, ins.fondo_emergencia / meta_fondo) if meta_fondo > 0 else 1.0,
                             "ahorro_mensual_6_meses": r2(ahorro_sugerido)},
        "reserva_inventario": r2(reserva_inventario), "utilidad_proyectada": r2(utilidad_mes),
        "distribucion": reparto["partes"], "faltante_obligatorio": reparto["faltante_obligatorio"],
        "pago_deuda_mensual": r2(pago_deuda_mensual), "pago_extra_deuda_sugerido": next(
            (p["asignado"] for p in reparto["partes"] if p["clave"] == "deuda_extra"), 0.0),
    }

    pronostico = {
        "metodo": pron.metodo, "pocos_datos": pron.pocos_datos, "aviso": "Pronóstico con pocos datos" if pron.pocos_datos else None,
        "precision": None if pron.precision is None else round(pron.precision, 1), "venta_base_diaria": r2(pron.base),
        "sigma_diaria": r2(sigma), "semanas": semanas_series, "total_horizonte": r2(total_horizonte), "semanas_horizonte": semanas,
        "total_horizonte_pesimista": r2(max(0.0, total_horizonte - Z_80 * sigma * (7 * semanas) ** 0.5)),
        "total_horizonte_optimista": r2(total_horizonte + Z_80 * sigma * (7 * semanas) ** 0.5),
    }
    resultado = {
        "tiene_datos": True, "fecha_corte": corte.isoformat(), "pronostico": pronostico, "mes": mes, "flujo": flujo_out,
        "equilibrio": equilibrio, "inventario": inventario, "consejos": consejos,
        "escenario": {"ventas_pct": esc.ventas_pct, "precios_pct": esc.precios_pct, "gasto_fijo_extra": esc.gasto_fijo_extra,
                      "deuda_monto": esc.deuda_monto, "deuda_tasa": esc.deuda_tasa, "deuda_plazo": esc.deuda_plazo},
    }
    resultado["alertas"] = [a.model_dump() for a in alertas_predictivas(ins, resultado)]
    return resultado


def _inventario(ins: Insumos, pron, efectivo: float, margen: float, fp: float, real: dict, corte: date) -> dict:
    hist28 = sum(real.get(corte - timedelta(days=i), 0.0) for i in range(28))
    fc28 = sum(pron.valores[:28])
    tendencia = min(1.15, max(0.85, fc28 / hist28)) if hist28 > 0 else 1.0
    filas, candidatas = [], []
    for p in ins.productos:
        demanda = statistics.fmean(p.unidades) * tendencia
        sigma_d = statistics.pstdev(p.unidades) if len(p.unidades) > 1 else 0.0
        ss = pf.stock_seguridad(sigma_d, p.lead_time)
        reorden = pf.punto_reorden(demanda, p.lead_time, ss)
        cobertura = pf.dias_cobertura(p.stock, demanda)
        cantidad = pf.cantidad_sugerida(demanda, p.lead_time, PERIODO_REVISION, ss, p.stock, p.empaque) if demanda > 0 else 0.0
        precio = p.precio * fp
        detenido = pf.monto_detenido(p.stock, demanda, p.costo) if demanda > 0 else p.stock * p.costo
        excesivo = cobertura is None and p.stock > 0 or (cobertura is not None and cobertura > pf.DIAS_EXCESO)
        filas.append({
            "id_producto": p.id, "nombre": p.nombre, "unidad": p.unidad, "existencias": r2(p.stock), "demanda_diaria": round(demanda, 2),
            "cobertura_dias": None if cobertura is None else round(cobertura, 1),
            "fecha_agotamiento": None if cobertura is None else (corte + timedelta(days=int(cobertura))).isoformat(),
            "lead_time": p.lead_time, "stock_seguridad": round(ss, 1), "punto_reorden": round(reorden, 1), "cantidad_sugerida": round(cantidad, 1),
            "costo_compra": r2(cantidad * p.costo), "semaforo": pf.semaforo_reabasto(cobertura, p.stock, p.lead_time, reorden),
            "excesivo": bool(excesivo), "monto_detenido": r2(detenido if excesivo else 0.0), "posponer": False,
            "ganancia_por_unidad": r2(precio - p.costo),
        })
        if cantidad > 0:
            candidatas.append(pf.CompraCandidata(p.id, cantidad * p.costo, (precio - p.costo) * demanda, cantidad))
    presupuesto = max(0.0, efectivo - ins.minimo_seguridad)
    comprar, posponer = pf.priorizar_compras(candidatas, presupuesto)
    for fila in filas:
        fila["posponer"] = fila["id_producto"] in posponer
    orden = {"rojo": 0, "amarillo": 1, "verde": 2, "sin_movimiento": 3}
    filas.sort(key=lambda r: (orden[r["semaforo"]], r["cobertura_dias"] if r["cobertura_dias"] is not None else 1e9))
    total_compra = sum(r["costo_compra"] for r in filas)
    return {
        "productos": filas, "presupuesto": r2(presupuesto), "total_compra_sugerida": r2(total_compra),
        "alcanza": not posponer, "pospuestos": [r["nombre"] for r in filas if r["posponer"]],
        "monto_excesivo": r2(sum(r["monto_detenido"] for r in filas)), "factor_tendencia": round(tendencia, 3),
    }


def alertas_predictivas(ins: Insumos, r: dict) -> list[Alerta]:
    alertas: list[Alerta] = []
    inv = r["inventario"]
    for p in [x for x in inv["productos"] if x["semaforo"] in ("rojo", "amarillo") and x["cantidad_sugerida"] > 0][:3]:
        dias = int(p["cobertura_dias"]) if p["cobertura_dias"] is not None else 0
        alertas.append(Alerta(
            id=f"pred-agota-{p['id_producto']}", codigo="producto_por_agotarse", nivel="rojo" if p["semaforo"] == "rojo" else "amarillo",
            titulo=f"{p['nombre']} se te acaba pronto",
            mensaje=f"Al ritmo actual, {p['nombre']} se acaba en {dias} días. Compra {numero(p['cantidad_sugerida'])} {p['unidad']} ({dinero(p['costo_compra'])}).",
            accion="Haz el pedido a tu proveedor.", modulo="proyecciones",
            metricas={"producto": p["nombre"], "dias": str(dias), "cantidad": f"{numero(p['cantidad_sugerida'])} {p['unidad']}", "costo": dinero(p["costo_compra"])}))
    prev = ins.ventas_mensuales_previas
    if prev:
        promedio = sum(prev) / len(prev)
        diferencia = r["mes"]["ventas"] / promedio - 1 if promedio > 0 else 0
        if diferencia < -0.10:
            alertas.append(Alerta(
                id="pred-ventas-abajo", codigo="ventas_abajo_de_lo_esperado", nivel="amarillo", titulo="Este mes vas abajo de lo normal",
                mensaje=f"Este mes vas {pct(abs(diferencia))} abajo de lo esperado: proyectamos {dinero(r['mes']['ventas'])} contra un promedio de {dinero(promedio)}.",
                accion="Revisa promociones o productos que dejaron de venderse.", modulo="proyecciones",
                metricas={"abajo": pct(abs(diferencia)), "proyectado": dinero(r["mes"]["ventas"]), "promedio": dinero(promedio)}))
    fl = r["flujo"]
    if fl["fecha_riesgo"]:
        c = fl["causa_riesgo"] or {"monto": 0, "concepto": "las ventas más bajas de lo normal"}
        alertas.append(Alerta(
            id="pred-efectivo-riesgo", codigo="efectivo_por_debajo_del_minimo", nivel="rojo", titulo="Tu efectivo podría quedar corto",
            mensaje=f"El día {fl['fecha_riesgo']} tu efectivo bajaría de {dinero(fl['minimo_seguridad'])} por {c['concepto']} ({dinero(c['monto'])}).",
            accion="Aparta dinero o mueve el pago si puedes.", modulo="proyecciones",
            metricas={"fecha": fl["fecha_riesgo"], "minimo": dinero(fl["minimo_seguridad"]), "pago": dinero(c["monto"]), "concepto": c["concepto"]}))
    if inv["monto_excesivo"] > 0:
        alertas.append(Alerta(
            id="pred-inventario-detenido", codigo="inventario_detenido", nivel="amarillo", titulo="Tienes dinero detenido en inventario",
            mensaje=f"Tienes {dinero(inv['monto_excesivo'])} detenidos en inventario que no se mueve.",
            accion="Haz una promoción o deja de comprar esos productos por ahora.", modulo="proyecciones",
            metricas={"monto": dinero(inv["monto_excesivo"])}))
    falta = r["consejos"]["faltante_obligatorio"]
    if falta > 0:
        alertas.append(Alerta(
            id="pred-utilidad-no-alcanza", codigo="utilidad_no_cubre_obligaciones", nivel="rojo", titulo="Tu utilidad no cubre impuestos y deudas",
            mensaje=f"La utilidad proyectada de {dinero(r['consejos']['utilidad_proyectada'])} no alcanza para impuestos y pagos de deuda: te faltan {dinero(falta)}.",
            accion="Revisa gastos o renegocia plazos de tus deudas.", modulo="proyecciones",
            metricas={"utilidad": dinero(r["consejos"]["utilidad_proyectada"]), "faltante": dinero(falta)}))
    return alertas


# ----------------------------------------------------------------------------- API de servicio


def proyeccion(conn: Connection, id_empresa: int, esc: Escenario | None = None, semanas: int = 8) -> dict:
    ins = cargar_insumos(conn, id_empresa)
    if ins is None:
        return {"tiene_datos": False}
    return calcular(ins, esc, semanas)


def contexto_deudas(conn: Connection, id_empresa: int) -> dict:
    """Ventas y utilidad operativa mensuales proyectadas (antes de pagar deudas) para los indicadores de deuda."""
    ins = cargar_insumos(conn, id_empresa)
    if ins is None:
        return {"ventas_mensuales": 0.0, "utilidad_operativa_mensual": 0.0}
    r = calcular(ins)
    ventas = r["mes"]["ventas"]
    utilidad = r["mes"]["utilidad"]
    return {"ventas_mensuales": ventas, "utilidad_operativa_mensual": utilidad, "fecha_corte": ins.corte}


def datos_para_clara(r: dict) -> dict:
    if not r.get("tiene_datos"):
        return {}
    m, fl, eq, c = r["mes"], r["flujo"], r["equilibrio"], r["consejos"]
    return {
        "mes": m["etiqueta"], "ventas_proyectadas_mes": dinero(m["ventas"]), "ventas_rango": f"{dinero(m['ventas_pesimista'])} a {dinero(m['ventas_optimista'])}",
        "utilidad_proyectada_mes": dinero(m["utilidad"]), "efectivo_actual": dinero(fl["efectivo_actual"]),
        "efectivo_fin_de_mes": dinero(fl["fin_de_mes"]["esperado"]), "efectivo_fin_de_mes_pesimista": dinero(fl["fin_de_mes"]["pesimista"]),
        "dias_de_colchon": None if fl["dias_colchon"] is None else numero(fl["dias_colchon"]),
        "fecha_de_riesgo": fl["fecha_riesgo"], "punto_de_equilibrio_mensual": dinero(eq["mensual"]) if eq["mensual"] is not None else None,
        "apartar_para_impuestos": dinero(c["apartado_impuestos"]), "ahorro_mensual_fondo_emergencia": dinero(c["fondo_emergencia"]["ahorro_mensual_6_meses"]),
        "faltante_para_obligaciones": dinero(c["faltante_obligatorio"]) if c["faltante_obligatorio"] > 0 else None,
        "inventario_detenido": dinero(r["inventario"]["monto_excesivo"]),
        "productos_por_comprar": [f"{p['nombre']}: {numero(p['cantidad_sugerida'])} {p['unidad']} ({dinero(p['costo_compra'])})"
                                  for p in r["inventario"]["productos"] if p["cantidad_sugerida"] > 0 and p["semaforo"] in ("rojo", "amarillo")][:3],
    }


def plantilla_clara(r: dict) -> str:
    if not r.get("tiene_datos"):
        return "Sube tus ventas para ver tus proyecciones."
    m, fl, c = r["mes"], r["flujo"], r["consejos"]
    partes = []
    if c["faltante_obligatorio"] > 0:
        partes.append(f"Ojo: la utilidad proyectada de {dinero(m['utilidad'])} no alcanza para impuestos y deudas; te faltan {dinero(c['faltante_obligatorio'])}.")
    if fl["fecha_riesgo"]:
        partes.append(f"Tu efectivo podría quedar por debajo de {dinero(fl['minimo_seguridad'])} el {fl['fecha_riesgo']}.")
    partes.append(f"Para {m['etiqueta']} estimamos ventas de {dinero(m['ventas'])} y una utilidad de {dinero(m['utilidad'])}; son estimaciones.")
    partes.append(f"Aparta {dinero(c['apartado_impuestos'])} para impuestos.")
    return " ".join(partes)

"""Servicio de finanzas: arma KPIs, estado de resultados, productos y flujo.

Es la única fuente de cifras de la plataforma: el dashboard, las alertas y el chatbot
consumen estas funciones, así que todos muestran exactamente los mismos números.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection

from app.finance import consultas as q
from app.finance import formulas as f
from app.finance.esquemas import (
    KPIs,
    CategoriaGasto,
    DatoClave,
    Finanzas,
    Flujo,
    LineaEstado,
    Periodo,
    ProductoMetricas,
    Productos,
    Proyeccion,
    PuntoEquilibrio,
    PuntoFlujoMensual,
    PuntoProyeccion,
    PuntoSaldo,
    PuntoSerie,
    ResumenInventario,
    Resumen,
    Variaciones,
)
from app.finance.periodos import (
    describir_periodo,
    etiqueta_mes,
    meses_en,
    numero_meses,
    periodo_anterior,
)
from app.forecasting.servicio import completar_dias, get_forecast_service

CERO = Decimal("0.00")
DIAS_RITMO_VENTA = 30   # ventana para el promedio diario de ventas (días de inventario)


def _num(valor: Decimal | None) -> float | None:
    return None if valor is None else float(valor)


def _periodo(desde: date, hasta: date) -> Periodo:
    return Periodo(desde=desde, hasta=hasta, etiqueta=describir_periodo(desde, hasta))


# ---------------------------------------------------------------------------
# KPIs y resumen
# ---------------------------------------------------------------------------


def _kpis(ventas_dia: list[dict], gastos_dia: list[dict]) -> KPIs:
    ventas = sum((v["ingreso"] for v in ventas_dia), CERO)
    costo = sum((v["costo"] for v in ventas_dia), CERO)
    fijos = sum((g["monto"] for g in gastos_dia if g["tipo"] == "fijo"), CERO)
    variables = sum((g["monto"] for g in gastos_dia if g["tipo"] == "variable"), CERO)
    bruta = f.utilidad_bruta(ventas, costo)
    neta = f.utilidad(bruta, fijos + variables)
    return KPIs(
        ventas=float(ventas), costo_ventas=float(costo), utilidad_bruta=float(bruta),
        gastos_operacion=float(fijos + variables), gastos_fijos=float(fijos), gastos_variables=float(variables),
        utilidad=float(neta), margen=_num(f.margen(neta, ventas)), margen_bruto=_num(f.margen(bruta, ventas)),
        unidades=float(sum((v["unidades"] for v in ventas_dia), CERO)),
    )


def kpis(conn: Connection, id_empresa: int, desde: date, hasta: date) -> KPIs:
    return _kpis(q.ventas_diarias(conn, id_empresa, desde, hasta), q.gastos_diarios(conn, id_empresa, desde, hasta))


def _variacion(actual: float, anterior: float) -> float | None:
    return _num(f.variacion(Decimal(str(actual)), Decimal(str(anterior))))


def serie(conn: Connection, id_empresa: int, desde: date, hasta: date, granularidad: str = "dia") -> list[PuntoSerie]:
    """Serie de ventas, costo, gastos y utilidad agrupada por día, semana o mes."""
    ventas_dia = q.ventas_diarias(conn, id_empresa, desde, hasta)
    gastos_dia = q.gastos_diarios(conn, id_empresa, desde, hasta)

    def clave(d: date) -> tuple[str, str]:
        if granularidad == "mes":
            return f"{d:%Y-%m}", etiqueta_mes(d.year, d.month)
        if granularidad == "semana":
            # Bloques de 7 días que terminan en `hasta`: la última semana siempre está completa.
            fin = hasta - timedelta(days=((hasta - d).days // 7) * 7)
            return fin.isoformat(), f"{fin:%d/%m}"
        return d.isoformat(), f"{d:%d/%m}"

    acumulado: dict[str, dict] = {}
    if granularidad == "mes":
        for anio, mes in meses_en(desde, hasta):
            k, etiqueta = clave(date(anio, mes, 1))
            acumulado[k] = {"etiqueta": etiqueta, "ventas": CERO, "costo": CERO, "gastos": CERO}
    else:
        actual = desde
        while actual <= hasta:
            k, etiqueta = clave(actual)
            acumulado.setdefault(k, {"etiqueta": etiqueta, "ventas": CERO, "costo": CERO, "gastos": CERO})
            actual += timedelta(days=1)
    for v in ventas_dia:
        k, _ = clave(v["fecha"])
        acumulado[k]["ventas"] += v["ingreso"]
        acumulado[k]["costo"] += v["costo"]
    for g in gastos_dia:
        k, _ = clave(g["fecha"])
        acumulado[k]["gastos"] += g["monto"]
    if granularidad == "semana" and (hasta - desde).days % 7 != 6 and len(acumulado) > 1:
        acumulado.pop(min(acumulado))      # primer bloque incompleto
    return [
        PuntoSerie(periodo=k, etiqueta=a["etiqueta"], ventas=float(a["ventas"]), costo=float(a["costo"]),
                   gastos=float(a["gastos"]), utilidad_bruta=float(a["ventas"] - a["costo"]),
                   utilidad=float(a["ventas"] - a["costo"] - a["gastos"]))
        for k, a in sorted(acumulado.items())
    ]


def resumen(conn: Connection, id_empresa: int, desde: date, hasta: date) -> Resumen:
    ventas_dia = q.ventas_diarias(conn, id_empresa, desde, hasta)
    gastos_dia = q.gastos_diarios(conn, id_empresa, desde, hasta)
    actual = _kpis(ventas_dia, gastos_dia)
    ant_desde, ant_hasta = periodo_anterior(desde, hasta)
    anterior = kpis(conn, id_empresa, ant_desde, ant_hasta)

    variaciones = Variaciones(
        ventas=_variacion(actual.ventas, anterior.ventas),
        costo_ventas=_variacion(actual.costo_ventas, anterior.costo_ventas),
        utilidad_bruta=_variacion(actual.utilidad_bruta, anterior.utilidad_bruta),
        gastos_operacion=_variacion(actual.gastos_operacion, anterior.gastos_operacion),
        utilidad=_variacion(actual.utilidad, anterior.utilidad),
        margen_pp=(actual.margen - anterior.margen) if actual.margen is not None and anterior.margen is not None else None,
    )
    granularidad = "dia" if (hasta - desde).days <= 62 else ("semana" if (hasta - desde).days <= 190 else "mes")
    puntos = serie(conn, id_empresa, desde, hasta, granularidad)

    dias_con_venta = [v for v in ventas_dia if v["ingreso"] > 0]
    dias_periodo = (min(hasta, q.rango_datos(conn, id_empresa)[1] or hasta) - desde).days + 1
    mejor = max(dias_con_venta, key=lambda v: v["ingreso"], default=None)
    peor = min(dias_con_venta, key=lambda v: v["ingreso"], default=None)
    efectivo = flujo_saldo(conn, id_empresa, hasta)
    datos = [
        DatoClave(etiqueta="Venta diaria promedio", formato="dinero",
                  valor=round(actual.ventas / max(dias_periodo, 1), 2), ayuda="Ventas del periodo entre los días del periodo"),
        DatoClave(etiqueta="Mejor día", formato="texto",
                  valor=f"{mejor['fecha']:%d/%m/%Y} · ${mejor['ingreso']:,.2f}" if mejor else None),
        DatoClave(etiqueta="Día con menos ventas", formato="texto",
                  valor=f"{peor['fecha']:%d/%m/%Y} · ${peor['ingreso']:,.2f}" if peor else None),
        DatoClave(etiqueta="Unidades vendidas", formato="numero", valor=actual.unidades),
        DatoClave(etiqueta="Margen bruto", formato="porcentaje", valor=actual.margen_bruto,
                  ayuda="Lo que te queda de cada peso vendido después de pagar la mercancía"),
        DatoClave(etiqueta="Gastos fijos", formato="dinero", valor=actual.gastos_fijos,
                  ayuda="Renta, sueldos y servicios: los pagas aunque no vendas"),
        DatoClave(etiqueta="Efectivo al cierre", formato="dinero", valor=float(efectivo),
                  ayuda="Saldo inicial + todo lo que entró − todo lo que salió"),
    ]
    return Resumen(
        periodo=_periodo(desde, hasta), periodo_anterior=_periodo(ant_desde, ant_hasta),
        kpis=actual, kpis_anterior=anterior, variaciones=variaciones, serie=puntos, datos_clave=datos,
    )


# ---------------------------------------------------------------------------
# Finanzas: estado de resultados, mensual, gastos, punto de equilibrio
# ---------------------------------------------------------------------------


def finanzas(conn: Connection, id_empresa: int, desde: date, hasta: date) -> Finanzas:
    ventas_dia = q.ventas_diarias(conn, id_empresa, desde, hasta)
    gastos_dia = q.gastos_diarios(conn, id_empresa, desde, hasta)
    k = _kpis(ventas_dia, gastos_dia)

    def pct(monto: float) -> float | None:
        return monto / k.ventas if k.ventas else None

    # Impuestos del periodo con el mismo cálculo del apartado de Impuestos (ISR + IVA neto a pagar).
    from app.impuestos.servicio import impuestos_del_periodo

    imp = impuestos_del_periodo(conn, id_empresa, desde, hasta)
    neta = round(k.utilidad - imp["total"], 2)
    regimen = f" ({imp['regimen_nombre']})" if imp["regimen_nombre"] else ""
    estado = [
        LineaEstado(clave="ventas", etiqueta="Lo que vendiste", termino_tecnico="Ventas netas",
                    monto=k.ventas, porcentaje=pct(k.ventas), nivel="ingreso"),
        LineaEstado(clave="costo_ventas", etiqueta="Lo que te costó la mercancía vendida", termino_tecnico="Costo de ventas",
                    monto=k.costo_ventas, porcentaje=pct(k.costo_ventas), nivel="resta"),
        LineaEstado(clave="utilidad_bruta", etiqueta="Lo que te queda después de la mercancía", termino_tecnico="Utilidad bruta",
                    monto=k.utilidad_bruta, porcentaje=pct(k.utilidad_bruta), nivel="subtotal"),
        LineaEstado(clave="gastos_fijos", etiqueta="Gastos fijos (renta, sueldos, servicios)", termino_tecnico="Gastos fijos de operación",
                    monto=k.gastos_fijos, porcentaje=pct(k.gastos_fijos), nivel="resta"),
        LineaEstado(clave="gastos_variables", etiqueta="Gastos variables (insumos, fletes, comisiones)",
                    termino_tecnico="Gastos variables de operación",
                    monto=k.gastos_variables, porcentaje=pct(k.gastos_variables), nivel="resta"),
        LineaEstado(clave="utilidad_antes_impuestos", etiqueta="Lo que ganaste antes de impuestos",
                    termino_tecnico="Utilidad antes de impuestos",
                    monto=k.utilidad, porcentaje=pct(k.utilidad), nivel="subtotal"),
        LineaEstado(clave="isr", etiqueta="ISR estimado", termino_tecnico=f"Impuesto sobre la renta de los meses del periodo{regimen}",
                    monto=imp["isr"], porcentaje=pct(imp["isr"]), nivel="resta"),
        LineaEstado(clave="iva", etiqueta="IVA a pagar al SAT",
                    termino_tecnico="Tus precios incluyen IVA: es el IVA cobrado menos el IVA de tus compras y gastos con factura",
                    monto=imp["iva"], porcentaje=pct(imp["iva"]), nivel="resta"),
        LineaEstado(clave="utilidad", etiqueta="Lo que ganaste después de impuestos", termino_tecnico="Utilidad neta (estimada)",
                    monto=neta, porcentaje=pct(neta), nivel="total"),
    ]

    mensual = serie(conn, id_empresa, desde, hasta, "mes")

    por_categoria: dict[str, Decimal] = defaultdict(lambda: CERO)
    tipos: dict[str, set[str]] = defaultdict(set)
    for g in gastos_dia:
        por_categoria[g["categoria"]] += g["monto"]
        tipos[g["categoria"]].add(g["tipo"])
    total_gastos = sum(por_categoria.values(), CERO)
    distribucion = sorted(
        (CategoriaGasto(categoria=c, tipo=next(iter(tipos[c])) if len(tipos[c]) == 1 else "mixto", monto=float(m),
                        porcentaje=float(m / total_gastos) if total_gastos else 0.0)
         for c, m in por_categoria.items()),
        key=lambda x: -x.monto,
    )

    meses = max(numero_meses(desde, hasta), 1)
    ventas_d = Decimal(str(k.ventas))
    costos_variables = Decimal(str(k.costo_ventas)) + Decimal(str(k.gastos_variables))
    mc = f.margen_contribucion(ventas_d, costos_variables)
    fijos_mes = f.redondear(Decimal(str(k.gastos_fijos)) / meses)
    ventas_mes = f.redondear(ventas_d / meses)
    pe = f.punto_equilibrio(fijos_mes, mc)
    seguridad = f.margen_seguridad(ventas_mes, pe)
    equilibrio = PuntoEquilibrio(
        gastos_fijos_mensuales=float(fijos_mes), margen_contribucion=_num(mc),
        punto_equilibrio_mensual=_num(pe), ventas_mensuales_promedio=float(ventas_mes),
        margen_seguridad_mensual=_num(seguridad), cubierto=None if seguridad is None else seguridad >= 0,
    )
    return Finanzas(periodo=_periodo(desde, hasta), estado_resultados=estado, mensual=mensual,
                    distribucion_gastos=distribucion, punto_equilibrio=equilibrio)


# ---------------------------------------------------------------------------
# Productos e inventario
# ---------------------------------------------------------------------------


def productos(conn: Connection, id_empresa: int, desde: date, hasta: date, umbral_dias: float) -> Productos:
    catalogo = q.productos(conn, id_empresa)
    vendidos = q.ventas_por_producto(conn, id_empresa, desde, hasta)
    corte = q.rango_datos(conn, id_empresa)[1] or hasta
    ritmo = q.ventas_por_producto(conn, id_empresa, corte - timedelta(days=DIAS_RITMO_VENTA - 1), corte)

    lista: list[ProductoMetricas] = []
    for p in catalogo:
        v = vendidos.get(p["id_producto"], {"unidades": CERO, "ingreso": CERO, "costo": CERO})
        venta_diaria = ritmo.get(p["id_producto"], {"unidades": CERO})["unidades"] / DIAS_RITMO_VENTA
        dias = f.dias_inventario(p["stock_actual"], venta_diaria)
        utilidad_p = v["ingreso"] - v["costo"]
        lista.append(ProductoMetricas(
            id_producto=p["id_producto"], nombre=p["sku_o_nombre"], categoria=p["categoria"], unidad=p["unidad"],
            unidades=float(v["unidades"]), ventas=float(v["ingreso"]), costo=float(v["costo"]),
            utilidad=float(utilidad_p), margen=_num(f.margen(utilidad_p, v["ingreso"])),
            precio_venta=float(p["precio_venta"]), costo_promedio=float(p["costo_promedio"]),
            margen_actual=_num(f.margen_producto(p["precio_venta"], p["costo_promedio"])),
            stock_actual=float(p["stock_actual"]), stock_minimo=float(p["stock_minimo"]),
            venta_diaria=round(float(venta_diaria), 2),
            dias_inventario=None if dias is None else round(float(dias), 1),
            semaforo=f.semaforo_inventario(dias, umbral_dias),
            valor_inventario=float(f.redondear(p["stock_actual"] * p["costo_promedio"])),
        ))
    lista.sort(key=lambda p: -p.utilidad)
    con_ventas = [p for p in lista if p.ventas > 0]
    inventario = ResumenInventario(
        verde=sum(p.semaforo == "verde" for p in lista), amarillo=sum(p.semaforo == "amarillo" for p in lista),
        rojo=sum(p.semaforo == "rojo" for p in lista), sin_movimiento=sum(p.semaforo == "sin_movimiento" for p in lista),
        valor_total=round(sum(p.valor_inventario for p in lista), 2),
    )
    return Productos(
        periodo=_periodo(desde, hasta), productos=lista, top_utilidad=con_ventas[:5],
        bajo_margen=sorted(con_ventas, key=lambda p: p.margen_actual if p.margen_actual is not None else 1)[:5],
        inventario=inventario,
    )


# ---------------------------------------------------------------------------
# Flujo de efectivo y proyección
# ---------------------------------------------------------------------------


def flujo_saldo(conn: Connection, id_empresa: int, al_dia: date) -> Decimal:
    """Efectivo al cierre de `al_dia`."""
    emp = q.empresa(conn, id_empresa) or {}
    acumulado = q.movimientos_acumulados(conn, id_empresa, al_dia + timedelta(days=1))
    return q.dec(emp.get("saldo_inicial")) + acumulado["entradas"] - acumulado["compras"] - acumulado["gastos"]


def _movimientos_por_dia(conn: Connection, id_empresa: int, desde: date, hasta: date) -> dict[date, dict[str, Decimal]]:
    dias: dict[date, dict[str, Decimal]] = defaultdict(lambda: {"entradas": CERO, "compras": CERO, "gastos": CERO})
    for v in q.ventas_diarias(conn, id_empresa, desde, hasta):
        dias[v["fecha"]]["entradas"] += v["ingreso"]
    for c in q.compras_diarias(conn, id_empresa, desde, hasta):
        dias[c["fecha"]]["compras"] += c["monto"]
    for g in q.gastos_diarios(conn, id_empresa, desde, hasta):
        dias[g["fecha"]]["gastos"] += g["monto"]
    return dias


def proyeccion(conn: Connection, id_empresa: int, dias: int = 30) -> Proyeccion | None:
    """Proyección de efectivo a `dias` con la línea base de ForecastService."""
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return None
    servicio = get_forecast_service()
    desde = corte - timedelta(days=servicio.ventana * 3)
    movimientos = _movimientos_por_dia(conn, id_empresa, desde, corte)
    entradas = completar_dias([(d, m["entradas"]) for d, m in movimientos.items()], desde, corte)
    salidas = completar_dias([(d, m["compras"] + m["gastos"]) for d, m in movimientos.items()], desde, corte)
    netos = completar_dias([(d, m["entradas"] - m["compras"] - m["gastos"]) for d, m in movimientos.items()],
                           desde, corte)
    acumulado = servicio.acumulado(netos, dias)
    saldo = float(flujo_saldo(conn, id_empresa, corte))
    prom_entradas = servicio.pronosticar(entradas, 1)[0].valor
    prom_salidas = servicio.pronosticar(salidas, 1)[0].valor
    puntos = [PuntoProyeccion(fecha=p.fecha, saldo=round(saldo + p.valor, 2), inferior=round(saldo + p.inferior, 2),
                              superior=round(saldo + p.superior, 2)) for p in acumulado]
    return Proyeccion(
        metodo=servicio.metodo, dias=dias, fecha_corte=corte, saldo_actual=round(saldo, 2),
        saldo_proyectado=puntos[-1].saldo, inferior=puntos[-1].inferior, superior=puntos[-1].superior,
        entradas_diarias=prom_entradas, salidas_diarias=prom_salidas, puntos=puntos,
    )


def flujo(conn: Connection, id_empresa: int, desde: date, hasta: date) -> Flujo:
    saldo = flujo_saldo(conn, id_empresa, desde - timedelta(days=1))
    saldo_inicial = saldo
    movimientos = _movimientos_por_dia(conn, id_empresa, desde, hasta)

    mensual_acum: dict[str, dict] = {}
    for anio, mes in meses_en(desde, hasta):
        mensual_acum[f"{anio}-{mes:02d}"] = {"etiqueta": etiqueta_mes(anio, mes), "entradas": CERO, "compras": CERO,
                                             "gastos": CERO}
    diario: list[PuntoSaldo] = []
    actual = desde
    while actual <= hasta:
        m = movimientos.get(actual)
        if m:
            saldo += m["entradas"] - m["compras"] - m["gastos"]
            bucket = mensual_acum[f"{actual:%Y-%m}"]
            for clave in ("entradas", "compras", "gastos"):
                bucket[clave] += m[clave]
        diario.append(PuntoSaldo(fecha=actual, saldo=float(saldo)))
        actual += timedelta(days=1)

    mensual: list[PuntoFlujoMensual] = []
    saldo_mes = saldo_inicial
    for clave, b in mensual_acum.items():
        neto = b["entradas"] - b["compras"] - b["gastos"]
        saldo_mes += neto
        mensual.append(PuntoFlujoMensual(periodo=clave, etiqueta=b["etiqueta"], entradas=float(b["entradas"]),
                                         compras=float(b["compras"]), gastos=float(b["gastos"]),
                                         neto=float(neto), saldo=float(saldo_mes)))
    total = {c: sum((b[c] for b in mensual_acum.values()), CERO) for c in ("entradas", "compras", "gastos")}
    return Flujo(
        periodo=_periodo(desde, hasta), saldo_inicial=float(saldo_inicial), entradas=float(total["entradas"]),
        compras=float(total["compras"]), gastos=float(total["gastos"]),
        saldo_final=float(saldo), mensual=mensual, diario=diario if len(diario) <= 400 else diario[:: len(diario) // 365 + 1],
        proyeccion=proyeccion(conn, id_empresa),
    )

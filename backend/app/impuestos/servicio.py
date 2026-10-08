"""Impuestos mensuales (ISR + IVA) con criterio de contador mexicano.

Las ventas se toman como cobradas el día en que se registran (comercio al contado) y las compras y
gastos como pagados el día en que se registran. Los precios incluyen IVA. Todo es determinista.
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import Connection, text

from app.finance import consultas as q
from app.finance.periodos import MESES, fin_de_mes, sumar_meses
from app.impuestos import formulas as f
from app.impuestos.clasificador import clasificar, tasa_iva_gasto
from app.impuestos.parametros import parametros, tasa_iva_sugerida

DISCLAIMER = ("Estimación informativa calculada con tus datos. No sustituye la declaración ni la asesoría de un contador. "
              "Verifica tasas y tarifas vigentes con el SAT.")


def _etiqueta(anio: int, mes: int) -> str:
    return f"{MESES[mes - 1].capitalize()} {anio}"


def fecha_limite(anio: int, mes: int, dia: int = 17) -> date:
    """El pago del mes M vence el día 17 del mes siguiente."""
    siguiente = sumar_meses(date(anio, mes, 1), 1)
    return siguiente.replace(day=min(dia, calendar.monthrange(siguiente.year, siguiente.month)[1]))


def configuracion(conn: Connection, id_empresa: int) -> dict:
    fila = conn.execute(text(
        "SELECT regimen_fiscal, tipo_persona, factura_a_morales, pct_ventas_morales, tiene_trabajadores, "
        "coeficiente_utilidad FROM empresas WHERE id_empresa = :e"), {"e": id_empresa}).mappings().first()
    fila = dict(fila)
    return {
        "regimen": f.codigo_regimen(fila["regimen_fiscal"], fila["tipo_persona"]),
        "regimen_texto": fila["regimen_fiscal"], "tipo_persona": fila["tipo_persona"],
        "factura_a_morales": bool(fila["factura_a_morales"]), "pct_ventas_morales": float(fila["pct_ventas_morales"] or 0),
        "tiene_trabajadores": bool(fila["tiene_trabajadores"]), "coeficiente_utilidad": float(fila["coeficiente_utilidad"] or 0),
    }


def _cargar(conn: Connection, id_empresa: int, desde: date, hasta: date, anio: int):
    """Ventas, compras y gastos del año agrupados por mes, ya separados en base e IVA."""
    productos = {p["id_producto"]: p for p in conn.execute(text(
        "SELECT id_producto, sku_o_nombre, categoria, tasa_iva FROM productos_cat WHERE id_empresa = :e"),
        {"e": id_empresa}).mappings()}

    def tasa(id_producto: int) -> float:
        p = productos.get(id_producto)
        if not p:
            return 0.16
        return float(p["tasa_iva"]) if p["tasa_iva"] is not None else tasa_iva_sugerida(p["categoria"], p["sku_o_nombre"], anio)

    rango = {"e": id_empresa, "d": desde.isoformat(), "h": (hasta + timedelta(days=1)).isoformat()}
    ventas = defaultdict(lambda: {"total": 0.0, "base": 0.0, "iva": 0.0})
    for r in conn.execute(text(
            "SELECT fecha, id_producto, ingreso FROM v_ventas_diarias WHERE id_empresa = :e AND fecha >= :d AND fecha < :h"),
            rango).mappings():
        fe, t, total = q.a_fecha(r["fecha"]), tasa(r["id_producto"]), float(r["ingreso"])
        b = ventas[fe.month]
        b["total"] += total
        b["base"] += f.base_sin_iva(total, t)
        b["iva"] += f.iva_incluido(total, t)

    compras = defaultdict(lambda: {"total": 0.0, "base": 0.0, "iva": 0.0})
    for r in conn.execute(text(
            "SELECT fecha, id_producto, SUM(cantidad * costo_unitario) AS monto FROM compras_producto "
            "WHERE id_empresa = :e AND fecha >= :d AND fecha < :h GROUP BY fecha, id_producto"), rango).mappings():
        fe, t, total = q.a_fecha(r["fecha"]), tasa(r["id_producto"]), float(r["monto"])
        b = compras[fe.month]
        b["total"] += total
        b["base"] += f.base_sin_iva(total, t)
        b["iva"] += f.iva_incluido(total, t)

    gastos = conn.execute(text(
        "SELECT id_gasto, fecha, concepto, categoria, tipo, monto, tiene_cfdi, medio_pago, uso FROM gastos_operativos "
        "WHERE id_empresa = :e AND fecha >= :d AND fecha < :h ORDER BY fecha"), rango).mappings().all()
    return ventas, compras, [dict(g) for g in gastos]


def _evaluar_gasto(g: dict, regimen: str, p: dict) -> dict:
    monto = float(g["monto"])
    c = clasificar(g["concepto"], g["categoria"], monto, bool(g["tiene_cfdi"]), g["medio_pago"], g["uso"], regimen,
                   p["iva"]["limite_pago_efectivo"], p["deducciones"])
    t = tasa_iva_gasto(g["concepto"], g["categoria"])
    base = f.base_sin_iva(monto, t)
    iva = f.iva_incluido(monto, t)
    # Si el gasto es corregible (sin CFDI / efectivo) lo que se pierde es la deducción y el IVA.
    return {"c": c, "base": base, "iva": iva, "t": t, "monto": monto,
            "iva_acreditable": iva if c.acredita_iva else 0.0,
            "base_deducible": base * c.porcentaje if g["uso"] != "personal" else 0.0}


def calcular(conn: Connection, id_empresa: int, mes_ref: date | None = None) -> dict:
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return {"tiene_datos": False, "aviso_legal": DISCLAIMER}
    mes_ref = (mes_ref or corte).replace(day=1)
    anio, mes_n = mes_ref.year, mes_ref.month
    p = parametros(anio)
    cfg = configuracion(conn, id_empresa)
    regimen = cfg["regimen"]
    ventas, compras, gastos = _cargar(conn, id_empresa, date(anio, 1, 1), fin_de_mes(mes_ref), anio)
    evaluados = [(g, _evaluar_gasto(g, regimen, p)) for g in gastos]

    gast_mes = defaultdict(lambda: {"iva_acreditable": 0.0, "base_deducible": 0.0})
    for g, e in evaluados:
        b = gast_mes[q.a_fecha(g["fecha"]).month]
        b["iva_acreditable"] += e["iva_acreditable"]
        b["base_deducible"] += e["base_deducible"]

    meses, saldo_favor, pagos_isr_previos = [], 0.0, 0.0
    ing_acum = ded_acum = 0.0
    for m in range(1, mes_n + 1):
        v, c, gm = ventas[m], compras[m], gast_mes[m]
        iva_acred = c["iva"] + gm["iva_acreditable"]
        iva = f.iva_a_pagar(v["iva"], iva_acred, 0.0, saldo_favor)
        saldo_favor = iva["saldo_a_favor"]
        ing_acum += v["base"]
        retenciones = v["base"] * cfg["pct_ventas_morales"] * p["resico"]["retencion_morales"] if cfg["factura_a_morales"] else 0.0
        ded_mes = c["base"] + gm["base_deducible"]
        ded_acum += ded_mes
        if regimen == "626":
            r = f.isr_resico(v["base"], p["resico"]["tabla_mensual"], retenciones)
            isr, detalle = r["isr_a_pagar"], {"tasa": r["tasa"]}
        elif regimen == "612":
            r = f.pago_provisional_612(ing_acum, ded_acum, 0.0, 0.0, p["tarifa_art_96_mensual"], m, pagos_isr_previos)
            isr, detalle = r["pago_provisional"], {"base_acumulada": f.r2(r["base"])}
        else:
            r = f.pago_provisional_601(ing_acum, cfg["coeficiente_utilidad"], p["moral"]["tasa_isr"], pagos_isr_previos)
            isr, detalle = r["pago_provisional"], {"base_acumulada": f.r2(r["base"])}
        if regimen != "626":
            pagos_isr_previos += isr
        meses.append({
            "periodo": f"{anio}-{m:02d}", "etiqueta": _etiqueta(anio, m), "ventas": f.r2(v["total"]), "ingresos": f.r2(v["base"]),
            "iva_trasladado": f.r2(v["iva"]), "iva_acreditable": f.r2(iva_acred), "iva_a_pagar": f.r2(iva["a_pagar"]),
            "saldo_a_favor": f.r2(iva["saldo_a_favor"]), "isr": f.r2(isr), "total": f.r2(isr + iva["a_pagar"]),
            "fecha_limite": fecha_limite(anio, m, p["dia_pago"]).isoformat(), "deducciones": f.r2(ded_mes), **detalle,
        })

    actual = meses[-1]
    ventas_mes = actual["ventas"]
    total_ytd = sum(x["total"] for x in meses)
    ingresos_ytd = sum(x["ingresos"] for x in meses)
    apartar_100 = f.r2(actual["total"] / ventas_mes * 100) if ventas_mes else None

    # Dinero que se pierde por no deducir (sólo causas corregibles) en el mes elegido.
    perdidos = [(g, e) for g, e in evaluados if e["c"].perdido_por and q.a_fecha(g["fecha"]).month == mes_n]
    tasa_marg = (0.0 if regimen == "626" else p["moral"]["tasa_isr"] if regimen == "601"
                 else f.tasa_marginal(max(0.0, ing_acum - ded_acum), p["tarifa_art_96_mensual"], mes_n))
    base_perdida = sum(e["base"] for _, e in perdidos)
    iva_perdido = sum(e["iva"] for _, e in perdidos)
    perdido = {
        "monto": f.r2(base_perdida * tasa_marg + iva_perdido), "isr": f.r2(base_perdida * tasa_marg), "iva": f.r2(iva_perdido),
        "gastos": len(perdidos), "tasa_marginal": tasa_marg,
        "sin_cfdi": f.r2(sum(e["monto"] for _, e in perdidos if e["c"].perdido_por == "sin_cfdi")),
        "efectivo": f.r2(sum(e["monto"] for _, e in perdidos if e["c"].perdido_por == "efectivo")),
    }

    anualiza = 12 / mes_n
    ded_anual = ded_acum * anualiza
    comparador = None
    if cfg["tipo_persona"] == "fisica":
        resico_anual = sum(f.isr_resico(x["ingresos"], p["resico"]["tabla_mensual"])["isr_causado"] for x in meses) * anualiza
        ae_anual = f.isr_tarifa(max(0.0, ingresos_ytd * anualiza - ded_anual), p["tarifa_art_96_mensual"], 12)
        elegible = ingresos_ytd * anualiza <= p["resico"]["limite_anual"]
        comparador = {
            "resico_anual": f.r2(resico_anual), "actividades_empresariales_anual": f.r2(ae_anual),
            "ahorro": f.r2(abs(resico_anual - ae_anual)), "elegible_resico": elegible,
            "conviene": ("resico" if resico_anual <= ae_anual else "actividades_empresariales") if elegible else "actividades_empresariales",
            "actual": "resico" if regimen == "626" else "actividades_empresariales",
            "nota": "Anualizado con tus meses del año. En RESICO los gastos no se deducen para ISR; en Actividades Empresariales sí.",
        }

    ptu_mensual = None
    if cfg["tiene_trabajadores"]:
        renta = max(0.0, ingresos_ytd * anualiza - ded_anual)
        ptu_mensual = {"anual_estimada": f.r2(f.ptu(renta, p["ptu"]["porcentaje"])),
                       "provision_mensual": f.r2(f.ptu(renta, p["ptu"]["porcentaje"]) / 12),
                       "fecha": f"{anio + 1}-05-30" if cfg["tipo_persona"] == "moral" else f"{anio + 1}-06-29"}

    limite = p["resico"]["limite_anual"]
    alerta_limite = None
    if regimen == "626":
        estado = f.limite_resico_alcanzado(ingresos_ytd, limite, p["resico"]["aviso_limite_pct"])
        alerta_limite = {"estado": estado, "ingresos_acumulados": f.r2(ingresos_ytd), "limite": limite,
                         "proyeccion_anual": f.r2(ingresos_ytd * anualiza)}

    # Calendario: pago del mes elegido y estimados de los siguientes con el promedio de los últimos 3 meses.
    ultimos = [x["total"] for x in meses[-3:]]
    promedio = sum(ultimos) / len(ultimos)
    calendario = [{"fecha": actual["fecha_limite"], "concepto": f"Pago de {_etiqueta(anio, mes_n)} (ISR + IVA)",
                   "monto": actual["total"], "estimado": False}]
    for k in (1, 2):
        mm = sumar_meses(mes_ref, k)
        calendario.append({"fecha": fecha_limite(mm.year, mm.month, p["dia_pago"]).isoformat(),
                           "concepto": f"Pago de {_etiqueta(mm.year, mm.month)} (estimado)", "monto": f.r2(promedio), "estimado": True})
    calendario.append({"fecha": f"{anio + 1}-0{3 if cfg['tipo_persona'] == 'moral' else 4}-{'31' if cfg['tipo_persona'] == 'moral' else '30'}",
                       "concepto": "Declaración anual", "monto": None, "estimado": True})
    if ptu_mensual:
        calendario.append({"fecha": ptu_mensual["fecha"], "concepto": "Pago de PTU a trabajadores", "monto": ptu_mensual["anual_estimada"], "estimado": True})

    explicacion_iva = None
    if actual["saldo_a_favor"] > 0 or (ventas_mes and actual["iva_a_pagar"] <= 0.01 * ventas_mes):
        explicacion_iva = ("Gran parte de lo que vendes (alimentos básicos) tiene IVA al 0 %, pero tus compras y gastos sí llevan IVA que puedes acreditar; "
                           "por eso pagas poco o nada de IVA y a veces te queda saldo a favor, que se acredita en los meses siguientes.")
    return {
        "tiene_datos": True, "anio": anio, "mes": f"{anio}-{mes_n:02d}", "mes_etiqueta": _etiqueta(anio, mes_n),
        "configuracion": {**cfg, "regimen_nombre": f.REGIMENES[regimen]}, "parametros_anio": p["anio"],
        "total_a_pagar": actual["total"], "isr": actual["isr"], "iva_a_pagar": actual["iva_a_pagar"],
        "saldo_a_favor": actual["saldo_a_favor"], "fecha_limite": actual["fecha_limite"],
        "apartar_por_cada_100": apartar_100, "tasa_efectiva_anual": f.r2(total_ytd / ingresos_ytd * 100) / 100 if ingresos_ytd else None,
        "total_acumulado_anio": f.r2(total_ytd), "meses": meses, "perdido_por_no_deducir": perdido,
        "comparador_regimen": comparador, "ptu": ptu_mensual, "limite_resico": alerta_limite,
        "calendario": calendario, "explicacion_iva": explicacion_iva,
        "mensaje_resico": ("En RESICO los gastos NO se deducen para ISR, pero sí sirven para acreditar IVA." if regimen == "626" else None),
        "aviso_legal": DISCLAIMER,
    }


def gastos_clasificados(conn: Connection, id_empresa: int, mes_ref: date | None = None, limite: int = 200) -> list[dict]:
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return []
    mes_ref = (mes_ref or corte).replace(day=1)
    p = parametros(mes_ref.year)
    regimen = configuracion(conn, id_empresa)["regimen"]
    filas = conn.execute(text(
        "SELECT id_gasto, fecha, concepto, categoria, tipo, monto, tiene_cfdi, medio_pago, uso FROM gastos_operativos "
        "WHERE id_empresa = :e AND fecha >= :d AND fecha < :h ORDER BY monto DESC"),
        {"e": id_empresa, "d": mes_ref.isoformat(), "h": (fin_de_mes(mes_ref) + timedelta(days=1)).isoformat()}).mappings().all()
    salida = []
    for g in filas[:limite]:
        e = _evaluar_gasto(dict(g), regimen, p)
        c = e["c"]
        salida.append({
            "id_gasto": g["id_gasto"], "fecha": q.a_fecha(g["fecha"]).isoformat(), "concepto": g["concepto"], "categoria": g["categoria"],
            "monto": f.r2(e["monto"]), "tiene_cfdi": bool(g["tiene_cfdi"]), "medio_pago": g["medio_pago"], "uso": g["uso"],
            "estado": c.estado, "porcentaje": c.porcentaje, "monto_deducible": c.monto_deducible, "motivo": c.motivo,
            "acredita_iva": c.acredita_iva, "corregible": c.perdido_por,
        })
    return salida


def resumen_para_proyeccion(conn: Connection, id_empresa: int) -> dict:
    """Datos que necesita el flujo proyectado: pago pendiente y tasa efectiva de impuestos sobre ventas."""
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return {"tasa_efectiva": 0.0, "pendiente": None}
    # Último mes cerrado (si el corte es fin de mes, es el mismo mes; si no, el anterior).
    ref = corte.replace(day=1) if corte == fin_de_mes(corte) else sumar_meses(corte.replace(day=1), -1)
    r = calcular(conn, id_empresa, ref)
    if not r.get("tiene_datos"):
        return {"tasa_efectiva": 0.0, "pendiente": None}
    actual = r["meses"][-1]
    tasa = actual["total"] / actual["ventas"] if actual["ventas"] else 0.0
    vence = date.fromisoformat(actual["fecha_limite"])
    return {"tasa_efectiva": tasa, "pendiente": {"monto": actual["total"], "fecha": vence} if vence > corte and actual["total"] > 0 else None,
            "dia_pago": parametros(ref.year)["dia_pago"]}


def datos_para_clara(r: dict) -> dict:
    """JSON con cifras ya calculadas y ya formateadas; es lo único que ve el LLM."""
    from app.finance.formato import dinero, pct

    if not r.get("tiene_datos"):
        return {}
    perd, comp = r["perdido_por_no_deducir"], r["comparador_regimen"]
    return {
        "mes": r["mes_etiqueta"], "regimen": r["configuracion"]["regimen_nombre"], "total_a_pagar": dinero(r["total_a_pagar"]),
        "isr": dinero(r["isr"]), "iva_a_pagar": dinero(r["iva_a_pagar"]), "saldo_a_favor_iva": dinero(r["saldo_a_favor"]),
        "fecha_limite": r["fecha_limite"], "apartar_por_cada_100_pesos": dinero(r["apartar_por_cada_100"]),
        "dinero_perdido_por_no_deducir": dinero(perd["monto"]),
        "ahorro_posible_cambiando_regimen": dinero(comp["ahorro"]) if comp and comp["conviene"] != comp["actual"] else None,
        "tasa_efectiva_anual": pct(r["tasa_efectiva_anual"]) if r["tasa_efectiva_anual"] is not None else None,
    }


def plantilla_clara(r: dict) -> str:
    from app.finance.formato import dinero

    if not r.get("tiene_datos"):
        return "Sube tus ventas para estimar tus impuestos."
    texto = (f"Para {r['mes_etiqueta']} estimamos que debes pagar al SAT {dinero(r['total_a_pagar'])} "
             f"({dinero(r['isr'])} de ISR y {dinero(r['iva_a_pagar'])} de IVA) a más tardar el {r['fecha_limite']}. ")
    if r["apartar_por_cada_100"] is not None:
        texto += f"Aparta unos {dinero(r['apartar_por_cada_100'])} de cada $100 que vendes. "
    perd = r["perdido_por_no_deducir"]
    if perd["monto"] > 0:
        texto += f"Por gastos sin factura o pagados en efectivo estás dejando de recuperar unos {dinero(perd['monto'])}. "
    texto += "Es una estimación; confírmala con tu contador."
    return texto

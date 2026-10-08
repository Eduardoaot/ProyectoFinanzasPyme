"""Panel de deudas: tarjetas, indicadores, estrategias de pago, gráficas y alertas (todo calculado en código)."""

from datetime import date, timedelta

from sqlalchemy import Connection

from app.alerts.reglas import Alerta
from app.deudas import consultas as dq
from app.deudas import formulas as f
from app.finance import consultas as q
from app.finance.formato import dinero, numero, pct
from app.finance.periodos import sumar_meses
from app.proyecciones import servicio as proy

DIFERENCIA_MINIMA_AVALANCHA = 500.0
PCT_EXTRA_DEFECTO = 0.25       # del dinero que sobra después de pagar las deudas, si no se indica otro monto
NOMBRE_TIPO = {
    "tarjeta_credito": "Tarjeta de crédito", "credito_simple": "Crédito simple", "credito_revolvente": "Crédito revolvente",
    "proveedor": "Proveedor", "prestamo_personal": "Préstamo personal", "arrendamiento": "Arrendamiento",
}


def _fecha_mes(corte: date, mes: int) -> date:
    return sumar_meses(corte.replace(day=1), mes)


def _tarjeta(d: dict, sim: f.DeudaSim, corte: date) -> dict:
    saldo = sim.saldo
    original = float(d["monto_original"] or 0)
    unico = f.simular([sim], "actual")
    revolvente = d["tipo"] in f.TIPOS_REVOLVENTES
    pago = f.pago_programado(sim, saldo)
    nunca = (unico.meses_totales is None)
    util = f.utilizacion(saldo, sim.limite) if revolvente else None
    proximo = dq.fecha_de_pago(d, corte, 1)
    if d["dia_limite_pago"]:
        este_mes = dq.fecha_de_pago(d, corte, 0)
        proximo = este_mes if este_mes > corte else proximo
    return {
        "id_deuda": d["id_deuda"], "acreedor": d["acreedor"], "tipo": d["tipo"], "tipo_texto": NOMBRE_TIPO[d["tipo"]],
        "monto_original": f.r2(original), "saldo_actual": f.r2(saldo), "tasa_interes_anual": float(d["tasa_interes_anual"]),
        "cat": None if d["cat"] is None else float(d["cat"]), "aplica_iva_intereses": bool(d["aplica_iva_intereses"]),
        "plazo_meses": d["plazo_meses"], "pago_mensual": f.r2(pago), "pago_mensual_capturado": None if d["pago_mensual"] is None else float(d["pago_mensual"]),
        "limite_credito": None if d["limite_credito"] is None else float(d["limite_credito"]), "fecha_inicio": d["fecha_inicio"].isoformat(),
        "dia_corte": d["dia_corte"], "dia_limite_pago": d["dia_limite_pago"], "comisiones_mensuales": float(d["comisiones_mensuales"] or 0),
        "tasa_moratoria_anual": None if d["tasa_moratoria_anual"] is None else float(d["tasa_moratoria_anual"]),
        "uso": d["uso"], "estado": d["estado"], "progreso": min(1.0, max(0.0, 1 - saldo / original)) if original > 0 else None,
        "utilizacion": util, "pago_minimo": f.pago_minimo_tarjeta(saldo, sim.limite, sim.tasa_anual, sim.aplica_iva) if revolvente else None,
        "pago_sin_intereses": f.r2(saldo) if revolvente else None, "nunca_baja": nunca,
        "meses_para_liquidar": unico.meses_totales, "fecha_liquidacion": None if nunca else _fecha_mes(corte, unico.meses_totales or 0).isoformat(),
        "interes_total": unico.interes_total, "proximo_pago": {"fecha": proximo.isoformat(), "monto": f.r2(pago + sim.comision)},
    }


def tabla_amortizacion(d: dict, corte: date) -> list[dict]:
    """Tabla del crédito con plazo: cuota fija sobre el saldo y los meses que faltan."""
    n = dq.meses_restantes(d, corte) or 0
    if n <= 0 or float(d["saldo_actual"]) <= 0:
        return []
    filas = f.tabla_amortizacion(float(d["saldo_actual"]), float(d["tasa_interes_anual"]), n, bool(d["aplica_iva_intereses"]))
    return [{"mes": x.mes, "fecha": _fecha_mes(corte, x.mes).isoformat(), "interes": x.interes, "iva": x.iva, "capital": x.capital,
             "pago": x.pago, "saldo": x.saldo} for x in filas]


def panel(conn: Connection, id_empresa: int, extra: float | None = None) -> dict:
    corte = q.rango_datos(conn, id_empresa)[1] or date.today()
    todas = dq.listar(conn, id_empresa)
    activas = [d for d in todas if d["estado"] != "liquidada"]
    sims = [dq.a_sim(d, corte) for d in activas]
    ctx = proy.contexto_deudas(conn, id_empresa)
    ventas_m, utilidad_m = ctx["ventas_mensuales"], ctx["utilidad_operativa_mensual"]

    if not activas:
        return {"hay_deudas": False, "deudas": [], "liquidadas": [d["acreedor"] for d in todas], "kpis": None, "alertas": [],
                "fecha_corte": corte.isoformat()}

    actual = f.simular(sims, "actual")
    pago_mensual_total = sum(f.pago_programado(s, s.saldo) + s.comision for s in sims)
    if extra is None:
        extra = round(max(0.0, utilidad_m - pago_mensual_total) * PCT_EXTRA_DEFECTO, 2)
    avalancha = f.simular(sims, "avalancha", extra)
    bola = f.simular(sims, "bola_de_nieve", extra)

    tarjetas = [_tarjeta(d, s, corte) for d, s in zip(activas, sims)]
    nombres = {d["id_deuda"]: d["acreedor"] for d in activas}
    deuda_total = sum(s.saldo for s in sims)
    saldo_12 = actual.meses[11].saldo_total if len(actual.meses) >= 12 else 0.0
    primero = actual.meses[0]
    tasa_prom = f.tasa_promedio_ponderada([(s.saldo, s.tasa_anual) for s in sims])
    fraccion_ventas = pago_mensual_total / ventas_m if ventas_m > 0 else None
    cobertura = f.dscr(utilidad_m, pago_mensual_total)
    tarjetas_rev = [t for t in tarjetas if t["utilizacion"] is not None]
    saldo_rev, limite_rev = sum(t["saldo_actual"] for t in tarjetas_rev), sum(t["limite_credito"] or 0 for t in tarjetas_rev)
    libre = None if actual.meses_totales is None else _fecha_mes(corte, actual.meses_totales)

    horizonte = max([x for x in (actual.meses_totales, avalancha.meses_totales, bola.meses_totales) if x is not None] or [24])
    horizonte = min(120, max(6, horizonte))
    saldo_series = [{"mes": 0, "fecha": corte.isoformat(), "actual": f.r2(deuda_total), "avalancha": f.r2(deuda_total), "bola_de_nieve": f.r2(deuda_total)}]
    for mes in range(1, horizonte + 1):
        def saldo_en(res: f.ResultadoSim) -> float:
            return res.meses[mes - 1].saldo_total if mes <= len(res.meses) else 0.0
        saldo_series.append({"mes": mes, "fecha": _fecha_mes(corte, mes).isoformat(), "actual": saldo_en(actual),
                             "avalancha": saldo_en(avalancha), "bola_de_nieve": saldo_en(bola)})
    barras = [{"mes": x.mes, "etiqueta": _fecha_mes(corte, x.mes).isoformat(), "capital": x.capital, "interes": x.interes}
              for x in actual.meses[:12]]

    limite60 = corte + timedelta(days=60)
    calendario = sorted(
        ({"fecha": fe.isoformat(), "acreedor": quien, "monto": f.r2(monto)} for fe, monto, quien in dq.pagos_programados(conn, id_empresa, corte, 3)
         if corte < fe <= limite60), key=lambda x: x["fecha"])
    proximos = {
        "7_dias": f.r2(sum(c["monto"] for c in calendario if date.fromisoformat(c["fecha"]) <= corte + timedelta(days=7))),
        "30_dias": f.r2(sum(c["monto"] for c in calendario if date.fromisoformat(c["fecha"]) <= corte + timedelta(days=30))),
    }

    def resumen_plan(res: f.ResultadoSim) -> dict:
        return {"interes_total": res.interes_total, "meses": res.meses_totales,
                "fecha_liquidacion": None if res.meses_totales is None else _fecha_mes(corte, res.meses_totales).isoformat(),
                "orden": [nombres[i] for i in res.orden]}
    plan_actual, plan_av, plan_bola = resumen_plan(actual), resumen_plan(avalancha), resumen_plan(bola)
    diferencia = f.r2(plan_bola["interes_total"] - plan_av["interes_total"])
    recomendada = "avalancha" if diferencia >= DIFERENCIA_MINIMA_AVALANCHA or extra <= 0 else "bola_de_nieve"
    capacidad = f.capacidad_endeudamiento(utilidad_m, pago_mensual_total, tasa_prom or 0.0)

    kpis = {
        "deuda_total": f.r2(deuda_total), "deuda_corto_plazo": f.r2(deuda_total - saldo_12), "pago_mensual_total": f.r2(pago_mensual_total),
        "proximos_pagos": proximos, "tasa_promedio_ponderada": tasa_prom, "costo_mensual": primero.interes,
        "pct_ventas": fraccion_ventas, "semaforo_pct_ventas": f.semaforo_peso_deuda(fraccion_ventas),
        "dscr": None if cobertura is None else round(cobertura, 2), "semaforo_dscr": f.semaforo_dscr(cobertura),
        "razon_deuda_utilidad_anual": deuda_total / (utilidad_m * 12) if utilidad_m > 0 else None,
        "fecha_libre": None if libre is None else libre.isoformat(), "capacidad_endeudamiento": capacidad,
        "utilizacion_tarjetas": saldo_rev / limite_rev if limite_rev > 0 else None,
        "utilidad_operativa_mensual": f.r2(utilidad_m), "ventas_mensuales": f.r2(ventas_m),
    }
    resultado = {
        "hay_deudas": True, "fecha_corte": corte.isoformat(), "deudas": tarjetas, "kpis": kpis,
        "estrategias": {"extra_mensual": f.r2(extra), "actual": plan_actual, "avalancha": plan_av, "bola_de_nieve": plan_bola,
                        "recomendada": recomendada, "ahorro_avalancha_vs_bola": diferencia},
        "saldo_series": saldo_series, "barras_pago": barras, "calendario": calendario,
    }
    resultado["alertas"] = [a.model_dump() for a in alertas(resultado)]
    return resultado


def alertas(r: dict) -> list[Alerta]:
    lista: list[Alerta] = []
    k = r["kpis"]
    for d in r["deudas"]:
        if d["nunca_baja"]:
            lista.append(Alerta(
                id=f"deuda-nunca-baja-{d['id_deuda']}", codigo="deuda_nunca_baja", nivel="rojo", titulo=f"{d['acreedor']}: la deuda nunca baja",
                mensaje=f"Con este pago de {dinero(d['pago_mensual'])} la deuda de {d['acreedor']} nunca baja: solo cubre intereses.",
                accion="Sube el pago mensual o renegocia con el acreedor.", modulo="deudas",
                metricas={"acreedor": d["acreedor"], "pago": dinero(d["pago_mensual"])}))
        if d["utilizacion"] is not None and d["utilizacion"] > 0.30:
            lista.append(Alerta(
                id=f"deuda-utilizacion-{d['id_deuda']}", codigo="tarjeta_muy_usada", nivel="rojo" if d["utilizacion"] > 0.80 else "amarillo",
                titulo=f"{d['acreedor']}: usas mucho tu límite",
                mensaje=f"Usas {pct(d['utilizacion'], 0)} del límite de {d['acreedor']} ({dinero(d['saldo_actual'])} de {dinero(d['limite_credito'])}). Conviene mantenerte debajo de 30%.",
                accion="Abona para bajar la utilización.", modulo="deudas",
                metricas={"acreedor": d["acreedor"], "utilizacion": pct(d["utilizacion"], 0), "saldo": dinero(d["saldo_actual"]), "limite": dinero(d["limite_credito"]), "meta": "30%"}))
        if d["tasa_interes_anual"] > 0.70:
            lista.append(Alerta(
                id=f"deuda-tasa-alta-{d['id_deuda']}", codigo="deuda_muy_cara", nivel="rojo", titulo=f"{d['acreedor']} te cuesta muy caro",
                mensaje=f"La deuda con {d['acreedor']} cobra {pct(d['tasa_interes_anual'], 0)} anual. Es la que más conviene pagar primero.",
                accion="Prioriza esta deuda o compara opciones para sustituirla.", modulo="deudas",
                metricas={"acreedor": d["acreedor"], "tasa": pct(d["tasa_interes_anual"], 0)}))
    if k["dscr"] is not None and k["dscr"] < 1.0:
        lista.append(Alerta(
            id="deuda-dscr", codigo="deuda_no_alcanza", nivel="rojo", titulo="Tu utilidad no alcanza para tus deudas",
            mensaje=f"Tu utilidad mensual proyectada de {dinero(k['utilidad_operativa_mensual'])} no alcanza para tus pagos de deuda de {dinero(k['pago_mensual_total'])} (cobertura {k['dscr']:.2f}).",
            accion="Evita nuevas deudas y busca bajar tus pagos o subir tus ventas.", modulo="deudas",
            metricas={"utilidad": dinero(k["utilidad_operativa_mensual"]), "pagos": dinero(k["pago_mensual_total"]), "cobertura": f"{k['dscr']:.2f}"}))
    if k["semaforo_pct_ventas"] != "verde" and k["pct_ventas"] is not None:
        lista.append(Alerta(
            id="deuda-pct-ventas", codigo="deuda_pesa_en_ventas", nivel="rojo" if k["semaforo_pct_ventas"] == "rojo" else "amarillo",
            titulo="Las deudas se llevan una parte importante de tus ventas",
            mensaje=f"{pct(k['pct_ventas'], 0)} de tus ventas se va en pagar deudas ({dinero(k['pago_mensual_total'])} de {dinero(k['ventas_mensuales'])} al mes).",
            accion="Revisa si puedes consolidar o alargar plazos.", modulo="deudas",
            metricas={"porcentaje": pct(k["pct_ventas"], 0), "pagos": dinero(k["pago_mensual_total"]), "ventas": dinero(k["ventas_mensuales"])}))
    cercanos = [c for c in r["calendario"] if date.fromisoformat(c["fecha"]) <= date.fromisoformat(r["fecha_corte"]) + timedelta(days=7)]
    if cercanos:
        lista.append(Alerta(
            id="deuda-vencimientos", codigo="pagos_proximos", nivel="amarillo", titulo="Tienes pagos de deuda esta semana",
            mensaje=f"En los próximos 7 días vencen {len(cercanos)} pagos por {dinero(k['proximos_pagos']['7_dias'])}.",
            accion="Aparta el dinero para no pagar moratorios.", modulo="deudas",
            metricas={"pagos": numero(len(cercanos)), "monto": dinero(k["proximos_pagos"]["7_dias"])}))
    orden = {"rojo": 0, "amarillo": 1, "verde": 2}
    return sorted(lista, key=lambda a: orden[a.nivel])


def datos_para_clara(r: dict) -> dict:
    if not r.get("hay_deudas"):
        return {}
    k, e = r["kpis"], r["estrategias"]
    return {
        "deuda_total": dinero(k["deuda_total"]), "pago_mensual_total": dinero(k["pago_mensual_total"]),
        "costo_mensual_de_intereses_y_comisiones": dinero(k["costo_mensual"]), "porcentaje_de_ventas_en_deudas": pct(k["pct_ventas"], 0) if k["pct_ventas"] is not None else None,
        "cobertura_dscr": None if k["dscr"] is None else f"{k['dscr']:.2f}", "libre_de_deudas": k["fecha_libre"] or "con el plan actual no se liquida",
        "estrategia_recomendada": "avalancha (pagar primero la deuda con la tasa más alta)" if e["recomendada"] == "avalancha" else "bola de nieve (pagar primero la deuda más pequeña)",
        "ahorro_avalancha_vs_bola_de_nieve": dinero(e["ahorro_avalancha_vs_bola"]), "pago_extra_mensual_considerado": dinero(e["extra_mensual"]),
        "orden_de_pago_avalancha": e["avalancha"]["orden"], "alertas": [a["titulo"] for a in r["alertas"]][:4],
    }


def plantilla_clara(r: dict) -> str:
    if not r.get("hay_deudas"):
        return "No tienes deudas registradas. Si agregas una, te ayudo a planear su pago."
    k, e = r["kpis"], r["estrategias"]
    texto = f"Debes en total {dinero(k['deuda_total'])} y pagas {dinero(k['pago_mensual_total'])} al mes. "
    if k["dscr"] is not None and k["dscr"] < 1.0:
        texto += "Tu utilidad estimada no alcanza para cubrir esos pagos. "
    if e["recomendada"] == "avalancha" and e["extra_mensual"] > 0:
        texto += f"Si abonas {dinero(e['extra_mensual'])} extra al mes empezando por la deuda más cara, ahorras {dinero(e['ahorro_avalancha_vs_bola'])} en intereses frente a bola de nieve. "
    texto += "Son estimaciones; revisa tus contratos."
    return texto

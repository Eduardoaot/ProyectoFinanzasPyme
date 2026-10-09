"""Temas de Clara que usan los módulos de proyecciones, deudas, impuestos y el glosario.

Igual que en `hechos.py`: el código calcula y arma las cifras; el LLM solo las redacta.
"""

import re
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

from app.chat import glosario
from app.chat import hechos as h
from app.chat.hechos import Contexto, Hechos
from app.chat.intenciones import sin_acentos
from app.deudas import servicio as deudas_srv
from app.finance import consultas as q
from app.finance.formato import dinero, numero, pct, pct_cambio, unidades
from app.finance.periodos import MESES, fin_de_mes, sumar_meses
from app.forecasting.tendencias import MESES_ANIO, EntradaProducto, MesProducto, TendenciaProducto, tendencias
from app.impuestos import servicio as impuestos_srv
from app.proyecciones import servicio as proy_srv

MESES_HISTORIA = 15             # 12 + 3: para comparar los últimos 3 meses contra los mismos del año pasado
DIAS_COMPRAS_RECIENTES = 45
HORIZONTE_DEFECTO = 2
EFECTO_VISIBLE = 0.005          # medio punto: menos que eso no vale la pena explicarlo
PALABRAS_VENTAS = ("vender", "vendera", "venta", "demanda", "unidades", "piezas", "salida")
MINIMO_UNIDADES_MES = 5         # con menos piezas al mes, un +200 % es ruido

_NUMEROS_TEXTO = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}


def _pts(valor: float) -> str:
    return f"{'+' if valor >= 0 else '-'}{abs(valor) * 100:.1f} pts"


# ---------------------------------------------------------------------------
# ¿Qué significa…?
# ---------------------------------------------------------------------------


def _con_deudas(ctx: Contexto) -> tuple[str, list[str], str]:
    r = deudas_srv.panel(ctx.conn, ctx.id_empresa)
    if not r["hay_deudas"]:
        return ("Con tus números", ["No tienes deudas registradas. Cuando agregues una en Deudas verás la comparación "
                                    "de los planes con tus cifras."], "")
    k, e = r["kpis"], r["estrategias"]

    def plan(nombre: str, p: dict) -> str:
        fin = f"terminarías en {p['meses']} meses" if p["meses"] is not None else "con ese pago no se termina de pagar"
        orden = f" · orden: {', '.join(p['orden'])}" if p["orden"] else ""
        return f"{nombre}: {dinero(p['interes_total'])} de intereses y {fin}{orden}"

    lineas = [
        f"Debes en total {dinero(k['deuda_total'])} y pagas {dinero(k['pago_mensual_total'])} al mes",
        f"Abono extra que considera el sistema: {dinero(e['extra_mensual'])} al mes",
        "Avalancha y bola de nieve mantienen lo que hoy pagas al mes: cuando terminas una deuda, ese pago pasa a la "
        "siguiente. En el plan actual, lo que se libera ya no se usa para pagar las demás",
        plan("Plan actual (sin abono extra)", e["actual"]),
        plan("Avalancha", e["avalancha"]),
        plan("Bola de nieve", e["bola_de_nieve"]),
        f"Plan sugerido: **{'avalancha' if e['recomendada'] == 'avalancha' else 'bola de nieve'}** (se sugiere avalancha "
        f"cuando te ahorra al menos {dinero(deudas_srv.DIFERENCIA_MINIMA_AVALANCHA)} en intereses)",
    ]
    dif = e["ahorro_avalancha_vs_bola"]
    if dif > 0:
        resumen = f"Con tus deudas, la avalancha te ahorra {dinero(dif)} de intereses frente a la bola de nieve."
    elif dif < 0:
        resumen = f"Con tus deudas, la bola de nieve te ahorra {dinero(-dif)} de intereses frente a la avalancha."
    else:
        resumen = "Con tus deudas, los dos planes te cuestan lo mismo en intereses; elige el que te motive más."
    return ("Con tus deudas", lineas, resumen)


def _desde(constructor: Callable[[Contexto], Hechos], indice: int = 0) -> Callable[[Contexto], tuple[str, list[str], str]]:
    def conector(ctx: Contexto) -> tuple[str, list[str], str]:
        hechos = constructor(ctx)
        if not hechos.secciones:
            return ("", [], "")
        titulo, lineas = hechos.secciones[min(indice, len(hechos.secciones) - 1)]
        return (f"Con tus números · {titulo}", lineas, "")      # el respaldo de otro tema se saldría del concepto
    return conector


def concepto(ctx: Contexto) -> Hechos:
    conceptos = glosario.buscar(sin_acentos(ctx.mensaje))
    if not conceptos:
        return fuera_de_alcance(ctx)
    secciones = []
    for c in conceptos:
        lineas = [c.definicion] + ([c.ejemplo] if c.ejemplo else []) + ([f"Dónde lo ves: {c.donde}"] if c.donde else [])
        secciones.append((c.titulo, lineas))
    resumenes = []
    for clave in dict.fromkeys(c.datos for c in conceptos if c.datos):
        titulo, lineas, resumen = CONECTORES[clave](ctx)
        if lineas:
            secciones.append((titulo, lineas))
        if resumen:
            resumenes.append(resumen)
    titulos = [c.titulo.lower() for c in conceptos]
    nombres = ", ".join(titulos[:-1]) + " y " + titulos[-1] if len(titulos) > 1 else titulos[0]
    return Hechos(
        titulo=f"¿Qué significa {nombres}?",
        secciones=secciones,
        respaldo=" ".join(resumenes),
        sugerencias=[f"¿Qué es {c.titulo.lower()}?" for c in glosario.GLOSARIO
                     if c not in conceptos and c.datos == conceptos[0].datos][:2] or ["Hazme un análisis completo"],
        aviso=any(c.datos in ("deudas", "impuestos") for c in conceptos),
        enfoque="Explica el concepto con palabras sencillas, como a alguien que no es contador, con una comparación "
                "de la vida diaria de una tienda. Si hay cifras del negocio, úsalas para aterrizarlo. No agregues cifras.",
        oraciones=4,
    )


# ---------------------------------------------------------------------------
# ¿Qué productos van a mejorar?
# ---------------------------------------------------------------------------


def horizonte_meses(mensaje: str, ultimo_mes: date | None = None) -> int:
    """Meses hacia adelante desde el último mes completo: "en 2 meses" → 2; "en diciembre" (desde septiembre) → 3."""
    texto = sin_acentos(mensaje)
    if ultimo_mes:
        for i, nombre in enumerate(MESES, start=1):
            if re.search(rf"\b{nombre}\b", texto):
                return (i - ultimo_mes.month) % MESES_ANIO or MESES_ANIO
    if m := re.search(r"(\d+)\s*mes", texto):
        return max(1, min(MESES_ANIO, int(m.group(1))))
    if m := re.search(r"\b(un|uno|dos|tres|cuatro|cinco|seis)\s+mes", texto):
        return _NUMEROS_TEXTO[m.group(1)]
    if "trimestre" in texto:
        return 3
    if "proximo mes" in texto or "siguiente mes" in texto:
        return 1
    return HORIZONTE_DEFECTO


def _meses_ventana(corte: date) -> list[date]:
    ultimo = corte.replace(day=1) if corte == fin_de_mes(corte) else sumar_meses(corte.replace(day=1), -1)
    return [sumar_meses(ultimo, -i) for i in range(MESES_HISTORIA - 1, -1, -1)]


def calcular_tendencias(ctx: Contexto, horizonte: int) -> tuple[list[TendenciaProducto], list]:
    meses = _meses_ventana(ctx.corte)
    indice = {(m.year, m.month): i for i, m in enumerate(meses)}
    acumulado: dict[int, list[list[float]]] = defaultdict(lambda: [[0.0, 0.0, 0.0] for _ in meses])
    for f in q.ventas_productos_diarias(ctx.conn, ctx.id_empresa, meses[0], fin_de_mes(meses[-1])):
        i = indice.get((f["fecha"].year, f["fecha"].month))
        if i is not None:
            celda = acumulado[f["id_producto"]][i]
            celda[0] += float(f["unidades"])
            celda[1] += float(f["ingreso"])
            celda[2] += float(f["costo"])
    compras = q.costo_compras_por_producto(ctx.conn, ctx.id_empresa, ctx.corte - timedelta(days=DIAS_COMPRAS_RECIENTES - 1), ctx.corte)
    entradas = [
        EntradaProducto(
            id_producto=p["id_producto"], nombre=p["sku_o_nombre"], unidad=p["unidad"], precio_lista=float(p["precio_venta"]),
            stock=float(p["stock_actual"]), meses=[MesProducto(*c) for c in acumulado[p["id_producto"]]],
            costo_compras_recientes=float(compras[p["id_producto"]]) if p["id_producto"] in compras else None)
        for p in q.productos(ctx.conn, ctx.id_empresa) if p["id_producto"] in acumulado
    ]
    return tendencias(entradas, horizonte), meses


def _motivo(t: TendenciaProducto) -> str:
    partes = []
    if t.efecto_precio >= EFECTO_VISIBLE:
        partes.append(f"tu precio de lista ({dinero(t.precio_lista)}) ya es mayor que lo que cobraste en promedio "
                      f"({dinero(t.precio_ultimo)})")
    elif t.efecto_precio <= -EFECTO_VISIBLE:
        partes.append(f"tu precio de lista ({dinero(t.precio_lista)}) es menor que lo que cobraste en promedio "
                      f"({dinero(t.precio_ultimo)})")
    if t.costo_compras is not None and t.efecto_costo >= EFECTO_VISIBLE:
        partes.append(f"tus compras recientes te salieron más baratas ({dinero(t.costo_compras)} vs {dinero(t.costo_ultimo)} "
                      f"por {t.unidad})")
    elif t.costo_compras is not None and t.efecto_costo <= -EFECTO_VISIBLE:
        partes.append(f"tus compras recientes te salieron más caras ({dinero(t.costo_compras)} vs {dinero(t.costo_ultimo)} "
                      f"por {t.unidad})")
    return "; ".join(partes)


def _linea_margen(t: TendenciaProducto, emoji: str) -> str:
    motivo = _motivo(t)
    return (f"{emoji} **{t.nombre}**: de {pct(t.margen_ultimo)} a {pct(t.margen_proyectado)} ({_pts(t.cambio_pts)})"
            + (f" — {motivo}" if motivo else ""))


def tendencia_productos(ctx: Contexto) -> Hechos:
    horizonte = horizonte_meses(ctx.mensaje, _meses_ventana(ctx.corte)[-1])
    lista, meses = calcular_tendencias(ctx, horizonte)
    plazo = f"{horizonte} {'mes' if horizonte == 1 else 'meses'}"
    mes_ultimo = MESES[meses[-1].month - 1]
    objetivo = sumar_meses(meses[-1], horizonte)
    mes_objetivo = f"{MESES[objetivo.month - 1]} {objetivo.year}"
    if not lista:
        return Hechos(titulo="¿Hacia dónde van tus productos?",
                      secciones=[("Sin datos suficientes", ["Necesito al menos 2 meses con ventas de un producto para estimar su tendencia."])],
                      respaldo="Todavía no tengo suficiente historia de ventas por producto.", usa_llm=False)

    if any(p in sin_acentos(ctx.mensaje) for p in PALABRAS_VENTAS):
        return _ventas_por_producto(lista, horizonte, mes_ultimo, mes_objetivo)
    return _margen_por_producto(lista, horizonte, plazo)


COMO_MARGEN = (f"Margen: comparo tu precio de lista con lo que cobraste el último mes, y el costo de tus compras de los "
               f"últimos {DIAS_COMPRAS_RECIENTES} días con el costo de lo que vendiste. El costo nuevo entra conforme "
               f"vendes lo que ya tienes en el anaquel.")
COMO_VENTAS = ("Ventas: tomo lo que vendiste en ese mismo mes el año pasado (así se respetan temporadas como regreso a "
               "clases o diciembre) y lo ajusto por cuánto vas arriba o abajo este año. Sin un año de historia uso la "
               "tendencia de los últimos 6 meses, que es menos confiable.")


def _ventas_por_producto(lista: list[TendenciaProducto], horizonte: int, mes_ultimo: str, mes_objetivo: str) -> Hechos:
    def linea(t: TendenciaProducto, emoji: str) -> str:
        u = t.unidades
        texto = (f"{emoji} **{t.nombre}**: unas {unidades(round(u.unidades), t.unidad)} (en {mes_ultimo} vendiste "
                 f"{unidades(round(t.unidades_ultimo), t.unidad)}")
        if u.metodo == "mismo_mes_anio_pasado":
            texto += (f"; el año pasado en ese mes fueron {unidades(round(u.mismo_mes_anio_pasado), t.unidad)} y este año "
                      f"vas {pct_cambio(u.crecimiento_anual)}")
        return texto + f") · confianza {u.confianza}"

    def diferencia(t: TendenciaProducto) -> float:
        return t.unidades.unidades - t.unidades_ultimo

    def umbral(t: TendenciaProducto) -> float:
        return max(1.0, 0.05 * t.unidades_ultimo)

    confiables = [t for t in lista if t.unidades.confianza != "baja"
                  and max(t.unidades_ultimo, t.unidades.unidades) >= MINIMO_UNIDADES_MES]
    suben = sorted((t for t in confiables if diferencia(t) > umbral(t)), key=lambda t: -diferencia(t))[:4]
    bajan = sorted((t for t in confiables if diferencia(t) < -umbral(t)), key=diferencia)[:4]
    lineas = [linea(t, "📈") for t in suben] + [linea(t, "📉") for t in bajan]

    partes = []
    if suben:
        partes.append(f"En {mes_objetivo} esperamos que {suben[0].nombre} venda más: unas "
                      f"{unidades(round(suben[0].unidades.unidades), suben[0].unidad)}.")
    if bajan:
        partes.append(f"{bajan[0].nombre} bajaría a unas {unidades(round(bajan[0].unidades.unidades), bajan[0].unidad)} "
                      f"después de vender {unidades(round(bajan[0].unidades_ultimo), bajan[0].unidad)} en {mes_ultimo}.")
    recomendaciones = []
    if suben:
        recomendaciones.append(f"Asegura existencias de los productos 📈 antes de {mes_objetivo}.")
    if bajan:
        recomendaciones.append("Compra menos de los productos 📉 para no quedarte con dinero detenido en inventario.")
    return Hechos(
        titulo=f"¿Qué productos van a vender más en {mes_objetivo}?",
        secciones=[(f"Ventas en unidades en {mes_objetivo}", lineas or [
                       "Ningún producto muestra un cambio claro en sus ventas: tus datos suben y bajan sin una dirección definida."]),
                   ("Cómo lo calculé", [COMO_VENTAS])],
        respaldo=" ".join(partes) or f"No veo cambios claros en las ventas de tus productos para {mes_objetivo}.",
        recomendaciones=recomendaciones,
        datos={"horizonte_meses": horizonte, "suben": [t.nombre for t in suben], "bajan": [t.nombre for t in bajan]},
        sugerencias=["¿Qué se me va a agotar?", "¿Qué productos van a mejorar su margen?", "¿Cuánto voy a vender el próximo mes?"],
        aviso=True,
        enfoque="Di qué productos venderían más y cuáles menos en ese mes y qué hacer con las compras. Aclara que es una "
                "estimación basada en el mismo mes del año pasado.",
    )


def _margen_por_producto(lista: list[TendenciaProducto], horizonte: int, plazo: str) -> Hechos:
    mejoran = [t for t in lista if t.clasificacion == "mejora"]
    empeoran = sorted((t for t in lista if t.clasificacion == "empeora"), key=lambda t: t.cambio_pts)
    estables = [t for t in lista if t.clasificacion == "estable"]
    secciones = [
        (f"Podrían mejorar su margen en {plazo}", [_linea_margen(t, "🟢") for t in mejoran[:5]]
         or ["Ninguno muestra señales claras de mejora: tus precios de lista y el costo de tus compras recientes son "
             "prácticamente iguales a los del último mes."]),
        (f"Podrían bajar su margen en {plazo}", [_linea_margen(t, "🔴") for t in empeoran[:5]]
         or ["Ninguno: no veo costos de compra más altos ni precios más bajos."]),
        ("Sin cambio a la vista", [f"{len(estables)} productos mantendrían un margen parecido al del último mes."]),
        ("Cómo lo calculé", [COMO_MARGEN]),
    ]

    if mejoran:
        t = mejoran[0]
        cuantos = "1 producto tiene" if len(mejoran) == 1 else f"{len(mejoran)} productos tienen"
        respaldo = (f"{cuantos} señales de mejorar su margen en {plazo}; el que más es {t.nombre}, "
                    f"que pasaría de {pct(t.margen_ultimo)} a {pct(t.margen_proyectado)}.")
    else:
        respaldo = f"Con tus datos, ningún producto muestra señales claras de mejorar su margen en {plazo}."
    if empeoran:
        respaldo += f" Ojo con {empeoran[0].nombre}: su margen bajaría a {pct(empeoran[0].margen_proyectado)}."

    recomendaciones = []
    if empeoran:
        recomendaciones.append("Revisa el precio de los productos en 🔴: su costo de compra subió y tu precio no.")
    if not mejoran:
        recomendaciones.append("Para mejorar margen: sube un poco el precio de los productos con margen más bajo o "
                               "negocia mejores costos con tus proveedores.")
    return Hechos(
        titulo=f"¿Qué productos van a mejorar su margen en {plazo}?",
        secciones=secciones,
        para_llm=[f"Plazo: {plazo}"] + [_linea_margen(t, "") for t in (mejoran[:3] + empeoran[:3])]
        + [f"{len(estables)} productos sin cambio de margen"],
        respaldo=respaldo, recomendaciones=recomendaciones,
        datos={"horizonte_meses": horizonte, "mejoran": [t.nombre for t in mejoran], "empeoran": [t.nombre for t in empeoran]},
        sugerencias=["¿Qué productos me dejan menos?", "¿Qué es el margen?", "¿Qué productos se van a vender más?"],
        aviso=True,
        enfoque="Di qué productos mejorarían o empeorarían su margen y por qué (precio o costo). Aclara que es una "
                "estimación basada en tus precios y compras recientes, no una certeza.",
    )


# ---------------------------------------------------------------------------
# Deudas, impuestos y pronóstico (con los mismos cálculos de sus páginas)
# ---------------------------------------------------------------------------


def deudas(ctx: Contexto) -> Hechos:
    r = deudas_srv.panel(ctx.conn, ctx.id_empresa)
    if not r["hay_deudas"]:
        return Hechos(titulo="Tus deudas", secciones=[("Deudas", ["No tienes deudas registradas."])],
                      respaldo=deudas_srv.plantilla_clara(r), usa_llm=False,
                      sugerencias=["¿Debería pedir un préstamo?", "¿Qué es la avalancha?"])
    k = r["kpis"]
    resumen = [
        f"Debes en total: **{dinero(k['deuda_total'])}**",
        f"Pagas al mes: {dinero(k['pago_mensual_total'])} (de eso, {dinero(k['costo_mensual'])} son intereses y comisiones)",
    ]
    if k["pct_ventas"] is not None:
        resumen.append(f"Se lleva {pct(k['pct_ventas'], 0)} de tus ventas del mes")
    if k["dscr"] is not None:
        resumen.append(f"Tu utilidad cubre tus pagos {k['dscr']:.2f} veces (cobertura; sano desde 1.25)")
    resumen.append(f"Libre de deudas: {k['fecha_libre'] or 'con los pagos actuales no se liquidan'}")
    _, planes, comparacion = _con_deudas(ctx)
    return Hechos(
        titulo="Tus deudas", secciones=[("Resumen", resumen), ("Planes de pago", planes[1:]),
                                        ("Alertas", [f"{h.EMOJI[a['nivel']]} **{a['titulo']}** — {a['mensaje']}" for a in r["alertas"][:4]])],
        para_llm=resumen + [comparacion],
        respaldo=deudas_srv.plantilla_clara(r),
        recomendaciones=list(dict.fromkeys(a["accion"] for a in r["alertas"]))[:3],
        sugerencias=["¿Qué es la avalancha?", "¿Qué es la bola de nieve?", "¿Me va a alcanzar el efectivo?"],
        aviso=True,
        enfoque="Di si las deudas pesan mucho y qué plan conviene. Presenta todo como opción a evaluar. No menciones bancos.",
    )


def impuestos(ctx: Contexto) -> Hechos:
    r = impuestos_srv.calcular(ctx.conn, ctx.id_empresa, ctx.hasta if ctx.periodo_explicito else None)
    if not r.get("tiene_datos"):
        return Hechos(titulo="Impuestos", secciones=[("Impuestos", ["Sube tus ventas para estimar tus impuestos."])],
                      respaldo=impuestos_srv.plantilla_clara(r), usa_llm=False, aviso=True)
    d = impuestos_srv.datos_para_clara(r)
    lineas = [
        f"Régimen: {d['regimen']}",
        f"A pagar por {d['mes']}: **{d['total_a_pagar']}** (ISR {d['isr']} + IVA {d['iva_a_pagar']})",
        f"Fecha límite: {d['fecha_limite']}",
    ]
    if r["saldo_a_favor"] > 0:
        lineas.append(f"Saldo a favor de IVA: {d['saldo_a_favor_iva']}")
    if r["apartar_por_cada_100"] is not None:
        lineas.append(f"Aparta {d['apartar_por_cada_100_pesos']} de cada $100 que vendes")
    if d["tasa_efectiva_anual"]:
        lineas.append(f"En lo que va del año pagas {d['tasa_efectiva_anual']} de tus ingresos en impuestos")
    extra = []
    if r["perdido_por_no_deducir"]["monto"] > 0:
        extra.append(f"Dejas de recuperar {d['dinero_perdido_por_no_deducir']} por gastos sin factura o pagados en efectivo")
    if d["ahorro_posible_cambiando_regimen"]:
        extra.append(f"Podrías ahorrar {d['ahorro_posible_cambiando_regimen']} al año en otro régimen (revísalo con tu contador)")
    if r.get("mensaje_resico"):
        extra.append(r["mensaje_resico"])
    return Hechos(
        titulo=f"Tus impuestos · {d['mes']}", secciones=[("Este mes", lineas), ("Para pagar menos (legalmente)", extra)],
        respaldo=impuestos_srv.plantilla_clara(r),
        recomendaciones=["Pide factura (CFDI) de tus compras y gastos del negocio.",
                         "Paga con transferencia o tarjeta los gastos de más de $2,000."] if extra else [],
        sugerencias=["¿Qué es el IVA acreditable?", "¿Qué es RESICO?", "¿Estoy ganando?"],
        aviso=True,
        enfoque="Di cuánto pagar y cuándo, y una forma de pagar menos legalmente. Es una estimación: que lo confirme con su contador.",
    )


def pronostico(ctx: Contexto) -> Hechos:
    r = proy_srv.proyeccion(ctx.conn, ctx.id_empresa)
    if not r.get("tiene_datos"):
        return Hechos(titulo="Proyección", secciones=[("Ventas", ["Sube tus ventas para ver tus proyecciones."])],
                      respaldo="Todavía no hay datos para proyectar.", usa_llm=False)
    p, m, fl = r["pronostico"], r["mes"], r["flujo"]
    ventas_l = [
        f"Ventas estimadas en {m['etiqueta']}: **{dinero(m['ventas'])}** (rango probable {dinero(m['ventas_pesimista'])} a "
        f"{dinero(m['ventas_optimista'])})",
        f"Utilidad estimada: {dinero(m['utilidad'])} (entre {dinero(m['utilidad_pesimista'])} y {dinero(m['utilidad_optimista'])})",
        f"Próximas {p['semanas_horizonte']} semanas: {dinero(p['total_horizonte'])} (entre {dinero(p['total_horizonte_pesimista'])} "
        f"y {dinero(p['total_horizonte_optimista'])})",
    ]
    metodo_l = [f"Venta base: {dinero(p['venta_base_diaria'])} al día (promedio de las últimas 8 semanas), ajustada por día de "
                f"la semana y por la tendencia de las últimas 12 semanas"]
    if p["precision"] is not None:
        metodo_l.append(f"Precisión medida con tus últimas 8 semanas: {numero(p['precision'])}%")
    if p["pocos_datos"]:
        metodo_l.append("Hay pocos datos: es un promedio simple, tómalo con cautela")
    efectivo_l = [f"Efectivo hoy: {dinero(fl['efectivo_actual'])}",
                  f"Al cierre de {m['etiqueta']}: {dinero(fl['fin_de_mes']['esperado'])} (pesimista {dinero(fl['fin_de_mes']['pesimista'])})"]
    if fl["fecha_riesgo"]:
        efectivo_l.append(f"🔴 El {fl['fecha_riesgo']} tu efectivo podría bajar de tu mínimo de {dinero(fl['minimo_seguridad'])}")
    return Hechos(
        titulo=f"Proyección · {m['etiqueta']}",
        secciones=[("Ventas y utilidad", ventas_l), ("Efectivo", efectivo_l), ("Cómo se calcula", metodo_l)],
        respaldo=proy_srv.plantilla_clara(r),
        datos={"metodo": p["metodo"], "precision": p["precision"]},
        sugerencias=["¿Qué es el rango probable?", "¿Qué productos van a vender más?", "¿Me va a alcanzar el efectivo?"],
        aviso=True,
        enfoque="Di cuánto se espera vender y ganar, y si el efectivo alcanza. Aclara que es una estimación con rango.",
    )


# ---------------------------------------------------------------------------
# Lo que Clara todavía no sabe responder
# ---------------------------------------------------------------------------


def fuera_de_alcance(ctx: Contexto) -> Hechos:
    return Hechos(
        titulo="Esa todavía no la sé responder",
        secciones=[("Lo que sí puedo hacer", [
            "Decirte si estás ganando, cuánto vendiste y en qué gastas, de cualquier mes o año.",
            "Decirte qué productos dejan más o menos, cuáles se van a agotar y cuáles podrían mejorar su margen.",
            "Proyectar tus ventas y tu efectivo, y explicarte tus deudas e impuestos.",
            "Explicarte términos como margen, punto de equilibrio, avalancha, bola de nieve o stock de seguridad.",
        ])],
        respaldo="No encontré cómo responder eso con los datos de tu negocio. Prueba preguntándolo de otra forma o con "
                 "alguna de las sugerencias.",
        sugerencias=["Hazme un análisis completo", "¿Qué productos van a mejorar su margen?", "¿Qué significa avalancha?"],
        usa_llm=False,
    )


CONECTORES: dict[str, Callable[[Contexto], tuple[str, list[str], str]]] = {
    "deudas": _con_deudas,
    "equilibrio": _desde(h.equilibrio),
    "margen": _desde(h.ganancia),
    "inventario": _desde(h.inventario),
    "flujo": _desde(h.flujo, indice=1),
    "impuestos": _desde(impuestos),
    "pronostico": _desde(pronostico),
}

CONSTRUCTORES: dict[str, Callable[[Contexto], Hechos]] = {
    **h.CONSTRUCTORES,
    "concepto": concepto, "tendencia_productos": tendencia_productos, "deudas": deudas,
    "impuestos": impuestos, "pronostico": pronostico, "fuera_de_alcance": fuera_de_alcance,
}

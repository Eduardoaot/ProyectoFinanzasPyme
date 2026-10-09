"""Hechos del chatbot: cifras calculadas por código para cada intención.

Cada constructor devuelve las secciones (ya formateadas) que verá el usuario, un resumen
corto para el LLM y un texto de respaldo por si Ollama no está disponible.
"""

import math
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Connection

from app.alerts.reglas import Alerta, evaluar, umbrales_empresa
from app.finance import servicio
from app.finance.formato import dinero, numero, pct, pct_cambio, unidades
from app.finance.periodos import describir_periodo
from app.impuestos import servicio as impuestos_srv

EMOJI = {"rojo": "🔴", "amarillo": "🟡", "verde": "🟢", "sin_movimiento": "⚪"}
AVISO = "Orientación general, no constituye asesoría financiera, contable ni fiscal."


@dataclass
class Contexto:
    conn: Connection
    id_empresa: int
    negocio: str
    giro: str
    desde: date
    hasta: date
    corte: date
    mensaje: str = ""
    periodo_explicito: bool = False

    @property
    def periodo(self) -> str:
        return describir_periodo(self.desde, self.hasta)


@dataclass
class Hechos:
    titulo: str
    secciones: list[tuple[str, list[str]]] = field(default_factory=list)
    para_llm: list[str] = field(default_factory=list)
    respaldo: str = ""
    recomendaciones: list[str] = field(default_factory=list)
    sugerencias: list[str] = field(default_factory=list)
    datos: dict = field(default_factory=dict)
    usa_llm: bool = True
    aviso: bool = False
    enfoque: str = ""
    oraciones: int = 3


def _alertas(ctx: Contexto) -> list[Alerta]:
    return evaluar(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)


def _linea_alerta(a: Alerta) -> str:
    return f"{EMOJI[a.nivel]} **{a.titulo}** — {a.mensaje}"


# ---------------------------------------------------------------------------
# Intenciones sin cálculos
# ---------------------------------------------------------------------------


def saludo(ctx: Contexto) -> Hechos:
    return Hechos(
        titulo=f"¡Hola! Soy Clara, tu asistente financiera de {ctx.negocio}",
        secciones=[("Puedo ayudarte con", [
            "¿Estoy ganando? — tu utilidad y margen de cualquier mes o año.",
            "¿Qué producto me deja más? — productos más y menos rentables.",
            "¿Qué productos van a mejorar su margen en 2 meses? — hacia dónde va cada producto.",
            "¿Dónde gasto demasiado? — tus gastos por categoría.",
            "¿Me va a alcanzar el efectivo? — flujo y proyección.",
            "¿Cuánto voy a vender el próximo mes? — pronóstico con rango pesimista y optimista.",
            "Tus deudas, tus impuestos, inventario por agotarse, punto de equilibrio y alertas.",
            "¿Qué significa…? — te explico términos como avalancha, bola de nieve, margen o punto de reorden.",
        ])],
        respaldo="Pregúntame con tus palabras o con el micrófono. Todas las cifras las calcula el sistema con tus "
                 "datos; yo te las explico.",
        sugerencias=["Hazme un análisis completo", "¿Qué productos van a mejorar su margen?", "¿Qué es la avalancha?"],
        usa_llm=False,
    )


def importar(ctx: Contexto) -> Hechos:
    return Hechos(
        titulo="Cómo subir tus datos desde Excel",
        secciones=[("Pasos", [
            "1. Entra a **Importar datos** en el menú lateral.",
            "2. Elige qué vas a subir: ventas, productos, compras o gastos.",
            "3. Si no tienes formato, descarga la **plantilla** de ejemplo y llénala.",
            "4. Arrastra tu archivo .xlsx o .csv (máximo 5 MB).",
            "5. Revisa cómo entendí tus columnas y corrige si hace falta.",
            "6. Confirma: te diré cuántas filas se cargaron y cuáles tuvieron errores.",
        ])],
        respaldo="Tus columnas pueden llamarse como quieras (por ejemplo \"P. Unitario\" o \"Precio\"): yo te propongo "
                 "a qué corresponde cada una y tú decides. Nada se guarda sin tu confirmación, y puedes deshacer una carga.",
        sugerencias=["¿Qué columnas necesita el archivo de ventas?", "Hazme un análisis completo"],
        usa_llm=False,
    )


# ---------------------------------------------------------------------------
# Intenciones con cifras
# ---------------------------------------------------------------------------


def _lineas_resultado(k) -> list[str]:
    lineas = [
        f"Vendiste: **{dinero(k.ventas)}**",
        f"Te costó la mercancía vendida: {dinero(k.costo_ventas)}",
        f"Te quedó después de la mercancía (utilidad bruta): {dinero(k.utilidad_bruta)}",
        f"Gastos de operación: {dinero(k.gastos_operacion)} (fijos {dinero(k.gastos_fijos)} · variables {dinero(k.gastos_variables)})",
        f"**Lo que ganaste: {dinero(k.utilidad)}**" if k.utilidad >= 0 else f"**Perdiste: {dinero(-k.utilidad)}**",
    ]
    if k.margen is not None:
        lineas.append(f"Margen: {pct(k.margen)} (de cada $100 que vendes te quedan {dinero(k.margen * 100)})")
    return lineas


def _cambio_utilidad(actual: float, anterior: float, variacion: float | None, ant: str) -> str:
    """Con cambio de signo o base muy pequeña el porcentaje confunde (-6092%): se explica con montos."""
    def estado(x: float) -> str:
        return f"ganar {dinero(x)}" if x >= 0 else f"perder {dinero(-x)}"
    if variacion is None or (actual >= 0) != (anterior >= 0) or abs(variacion) > 3:
        return f"Lo que ganaste: pasaste de {estado(anterior)} en {ant} a {estado(actual)}"
    return f"Lo que ganaste: {pct_cambio(variacion)} ({dinero(anterior)} en {ant})"


def _explicacion(v, ant: str) -> str:
    """Qué explica el resultado, calculado por código para que la IA no lo invente."""
    if v.gastos_operacion is not None and v.ventas is not None and v.gastos_operacion - v.ventas > 0.05:
        return f"Explicación: tus gastos de operación cambiaron {pct_cambio(v.gastos_operacion)} y tus ventas {pct_cambio(v.ventas)} frente a {ant}"
    if v.costo_ventas is not None and v.ventas is not None and v.costo_ventas - v.ventas > 0.05:
        return f"Explicación: tu costo de mercancía cambió {pct_cambio(v.costo_ventas)} y tus ventas {pct_cambio(v.ventas)} frente a {ant}"
    if v.ventas is not None:
        return f"Explicación: tus ventas cambiaron {pct_cambio(v.ventas)} frente a {ant}"
    return "Explicación: no hay periodo anterior para comparar"


def ganancia(ctx: Contexto) -> Hechos:
    r = servicio.resumen(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    k, v, ant = r.kpis, r.variaciones, r.periodo_anterior.etiqueta
    comparacion = [
        f"Ventas: {pct_cambio(v.ventas)} ({dinero(r.kpis_anterior.ventas)} en {ant})",
        f"Gastos de operación: {pct_cambio(v.gastos_operacion)} ({dinero(r.kpis_anterior.gastos_operacion)} en {ant})",
        _cambio_utilidad(k.utilidad, r.kpis_anterior.utilidad, v.utilidad, ant),
    ]
    if v.margen_pp is not None:
        comparacion.append(f"Margen: {'+' if v.margen_pp >= 0 else '-'}{abs(v.margen_pp) * 100:.1f} puntos")
    if k.utilidad >= 0:
        respaldo = f"Sí, estás ganando: en {ctx.periodo} te quedaron {dinero(k.utilidad)} después de pagar mercancía y gastos."
    else:
        respaldo = f"En {ctx.periodo} perdiste {dinero(-k.utilidad)}: entre mercancía y gastos salió más de lo que vendiste."
    return Hechos(
        titulo=f"¿Estás ganando? · {ctx.periodo}",
        secciones=[("Tus números", _lineas_resultado(k)), (f"Frente a {ant}", comparacion)],
        respaldo=respaldo,
        para_llm=[
            f"Periodo: {ctx.periodo}",
            f"Resultado: {'ganaste' if k.utilidad >= 0 else 'perdiste'} {dinero(abs(k.utilidad))}",
            f"Ventas: {dinero(k.ventas)}", f"Margen: {pct(k.margen)}",
            _explicacion(v, ant),
        ],
        datos={"kpis": k.model_dump(), "variaciones": v.model_dump()},
        sugerencias=["¿En qué gasto más?", "¿Qué producto me deja más?", "Compárame con el mes anterior"],
        enfoque="Di claramente si gana o pierde y qué lo explica.",
    )


def ventas(ctx: Contexto) -> Hechos:
    r = servicio.resumen(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    k, v = r.kpis, r.variaciones
    lineas = [
        f"Vendiste: **{dinero(k.ventas)}** ({numero(k.unidades)} unidades)",
        f"Frente a {r.periodo_anterior.etiqueta}: {pct_cambio(v.ventas)} ({dinero(r.kpis_anterior.ventas)})",
    ]
    lineas += [f"{d.etiqueta}: {d.valor if d.formato == 'texto' else dinero(d.valor)}"
               for d in r.datos_clave if d.etiqueta in ("Venta diaria promedio", "Mejor día", "Día con menos ventas")]
    secciones = [("Tus ventas", lineas)]
    if (ctx.hasta - ctx.desde).days > 40:
        mensual = servicio.serie(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta, "mes")
        secciones.append(("Mes por mes", [f"{p.etiqueta}: {dinero(p.ventas)}" for p in mensual]))
    return Hechos(
        titulo=f"Tus ventas · {ctx.periodo}", secciones=secciones,
        respaldo=f"En {ctx.periodo} vendiste {dinero(k.ventas)}, {pct_cambio(v.ventas)} frente a {r.periodo_anterior.etiqueta}.",
        datos={"ventas": k.ventas, "variacion": v.ventas},
        sugerencias=["¿Cuánto me voy a vender el próximo mes?", "¿Qué producto se vende más?"],
        enfoque="Explica si las ventas van bien o mal y por qué podría ser (temporada, días).",
    )


def _productos(ctx: Contexto):
    u = umbrales_empresa(ctx.conn, ctx.id_empresa)
    return servicio.productos(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta, u.dias_inventario_bajo)


def productos_top(ctx: Contexto) -> Hechos:
    p = _productos(ctx)
    top = [f"{i}. **{x.nombre}**: te dejó {dinero(x.utilidad)} ({unidades(x.unidades, x.unidad)}, margen {pct(x.margen)})"
           for i, x in enumerate(p.top_utilidad, start=1)]
    vendidos = sorted((x for x in p.productos if x.unidades > 0), key=lambda x: -x.ventas)[:3]
    return Hechos(
        titulo=f"Productos que más te dejan · {ctx.periodo}",
        secciones=[("Top 5 por ganancia", top),
                   ("Los que más venden (en pesos)", [f"{x.nombre}: {dinero(x.ventas)}" for x in vendidos])],
        respaldo=f"Tu producto estrella es {p.top_utilidad[0].nombre}: te dejó {dinero(p.top_utilidad[0].utilidad)} en {ctx.periodo}."
        if p.top_utilidad else "No hubo ventas en este periodo.",
        datos={"top": [x.model_dump() for x in p.top_utilidad]},
        sugerencias=["¿Qué productos me dejan menos?", "¿Qué se me va a agotar?"],
        enfoque="Explica qué tienen en común los productos que más dejan y cómo aprovecharlos.",
    )


def productos_bajo(ctx: Contexto) -> Hechos:
    p = _productos(ctx)
    u = umbrales_empresa(ctx.conn, ctx.id_empresa)
    lineas = []
    for x in p.bajo_margen:
        marca = "🔴 " if x.margen_actual is not None and x.margen_actual < u.margen_producto_bajo else ""
        lineas.append(f"{marca}**{x.nombre}**: precio {dinero(x.precio_venta)}, costo {dinero(x.costo_promedio)}, "
                      f"te quedan {dinero(x.precio_venta - x.costo_promedio)} por {x.unidad} (margen {pct(x.margen_actual)})")
    peor = p.bajo_margen[0] if p.bajo_margen else None
    return Hechos(
        titulo=f"Productos con menor margen · {ctx.periodo}",
        secciones=[("Los 5 que menos te dejan por unidad", lineas)],
        respaldo=f"El que menos te deja es {peor.nombre}, con margen de {pct(peor.margen_actual)}." if peor else "Sin datos.",
        recomendaciones=["Revisa si puedes subir un poco el precio de los productos en 🔴.",
                         "Compara proveedores: a veces el mismo producto cuesta menos en otro lado.",
                         "Si un producto atrae clientes aunque deje poco, cuida que no te falte."],
        datos={"bajo_margen": [x.model_dump() for x in p.bajo_margen]},
        sugerencias=["¿Qué productos me dejan más?", "¿Subió el costo de algún producto?"],
        enfoque="Explica el riesgo de vender productos con margen bajo, sin calcular nada nuevo.",
    )


def inventario(ctx: Contexto) -> Hechos:
    p = _productos(ctx)
    criticos = sorted((x for x in p.productos if x.semaforo in ("rojo", "amarillo")), key=lambda x: x.dias_inventario or 0)
    lineas = []
    for x in criticos[:8]:
        sugerido = max(0, math.ceil(x.venta_diaria * 14 - x.stock_actual))
        lineas.append(f"{EMOJI[x.semaforo]} **{x.nombre}**: quedan {unidades(x.stock_actual, x.unidad)} "
                      f"(~{numero(x.dias_inventario)} días). Para 2 semanas compra unas {unidades(sugerido, x.unidad)}.")
    inv = p.inventario
    return Hechos(
        titulo="Tu inventario",
        secciones=[
            ("Semáforo", [f"🟢 Bien: {inv.verde} productos", f"🟡 Atención: {inv.amarillo}", f"🔴 Por agotarse: {inv.rojo}",
                          f"Valor de tu inventario (a costo): {dinero(inv.valor_total)}"]),
            ("Lo que conviene resurtir", lineas or ["Nada urgente: todos tus productos tienen inventario suficiente."]),
        ],
        respaldo=f"Tienes {inv.rojo} productos por agotarse y {inv.amarillo} que conviene vigilar."
        if inv.rojo or inv.amarillo else "Tu inventario está sano.",
        datos={"inventario": inv.model_dump(), "criticos": [x.model_dump() for x in criticos[:8]]},
        sugerencias=["¿Me alcanza el efectivo para comprar?", "¿Qué productos me dejan más?"],
        enfoque="Prioriza qué comprar primero. Las cantidades sugeridas ya están calculadas.",
    )


def gastos(ctx: Contexto) -> Hechos:
    fz = servicio.finanzas(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    r = servicio.resumen(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    lineas = [f"{g.categoria} ({g.tipo}): {dinero(g.monto)} · {pct(g.porcentaje)}" for g in fz.distribucion_gastos[:8]]
    k = r.kpis
    resumen_l = [
        f"Gastos de operación: **{dinero(k.gastos_operacion)}** ({pct(k.gastos_operacion / k.ventas) if k.ventas else 'sin ventas'} de tus ventas)",
        f"Fijos: {dinero(k.gastos_fijos)} · Variables: {dinero(k.gastos_variables)}",
        f"Frente a {r.periodo_anterior.etiqueta}: {pct_cambio(r.variaciones.gastos_operacion)}",
    ]
    mayor = fz.distribucion_gastos[0] if fz.distribucion_gastos else None
    return Hechos(
        titulo=f"¿En qué se va tu dinero? · {ctx.periodo}",
        secciones=[("Resumen", resumen_l), ("Por categoría", lineas)],
        respaldo=f"Tu gasto más grande es {mayor.categoria}: {dinero(mayor.monto)} ({pct(mayor.porcentaje)} de tus gastos)."
        if mayor else "No hay gastos registrados en este periodo.",
        datos={"distribucion": [g.model_dump() for g in fz.distribucion_gastos]},
        sugerencias=["¿Cuál es mi punto de equilibrio?", "¿Estoy ganando?"],
        enfoque="Señala el gasto más pesado y si parece razonable; sugiere una forma de controlarlo.",
    )


def _lineas_proyeccion(proy) -> list[str]:
    return [
        f"Efectivo al {proy.fecha_corte:%d/%m/%Y}: **{dinero(proy.saldo_actual)}**",
        f"Al día entran en promedio {dinero(proy.entradas_diarias)} y salen {dinero(proy.salidas_diarias)}",
        f"En 30 días tendrías: **{dinero(proy.saldo_proyectado)}** (rango probable {dinero(proy.inferior)} a {dinero(proy.superior)})",
    ]


def flujo(ctx: Contexto) -> Hechos:
    fl = servicio.flujo(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    proy = fl.proyeccion
    periodo_l = [
        f"Efectivo al inicio: {dinero(fl.saldo_inicial)}",
        f"Entró por ventas: {dinero(fl.entradas)}",
        f"Salió en compras de mercancía: {dinero(fl.compras)}",
        f"Salió en gastos: {dinero(fl.gastos)}",
        f"Efectivo al final: **{dinero(fl.saldo_final)}**",
    ]
    secciones = [(f"Tu efectivo en {ctx.periodo}", periodo_l)]
    if proy:
        secciones.append(("Proyección a 30 días (si sigues al mismo ritmo)", _lineas_proyeccion(proy)))
    alcanza = proy is None or proy.saldo_proyectado >= 0
    return Hechos(
        titulo="¿Te va a alcanzar el efectivo?", secciones=secciones,
        respaldo=("Al ritmo actual, sí te alcanza para los próximos 30 días." if alcanza else
                  f"Cuidado: al ritmo de los últimos 30 días tu efectivo quedaría en {dinero(proy.saldo_proyectado)}."),
        recomendaciones=[] if alcanza else ["Pospón compras que no sean urgentes.", "Revisa qué gastos puedes recortar este mes."],
        datos={"flujo": {k: v for k, v in fl.model_dump().items() if k not in ("diario", "mensual")}},
        sugerencias=["¿En qué gasto más?", "¿Debería pedir un préstamo?"],
        enfoque="Responde si le alcanza el efectivo y qué hacer. Es una proyección simple, dilo.",
    )


def equilibrio(ctx: Contexto) -> Hechos:
    pe = servicio.finanzas(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta).punto_equilibrio
    lineas = [
        f"Gastos fijos al mes: {dinero(pe.gastos_fijos_mensuales)}",
        f"De cada $100 que vendes, después de mercancía y gastos variables te quedan "
        f"{dinero((pe.margen_contribucion or 0) * 100)} para cubrir gastos fijos (margen de contribución {pct(pe.margen_contribucion)})",
        f"**Necesitas vender al mes: {dinero(pe.punto_equilibrio_mensual)}** para no perder",
        f"Vendes en promedio: {dinero(pe.ventas_mensuales_promedio)} al mes",
    ]
    if pe.margen_seguridad_mensual is not None:
        if pe.margen_seguridad_mensual >= 0:
            lineas.append(f"Margen de seguridad: tus ventas podrían bajar {dinero(pe.margen_seguridad_mensual)} al mes antes de perder")
        else:
            lineas.append(f"Te faltan {dinero(-pe.margen_seguridad_mensual)} al mes para llegar al punto de equilibrio")
    return Hechos(
        titulo=f"Tu punto de equilibrio · {ctx.periodo}", secciones=[("Para no perder", lineas)],
        respaldo=f"Necesitas vender {dinero(pe.punto_equilibrio_mensual)} al mes para cubrir todos tus gastos.",
        datos={"punto_equilibrio": pe.model_dump()},
        sugerencias=["¿Estoy ganando?", "¿En qué gasto más?"],
        enfoque="Explica qué significa el punto de equilibrio con un ejemplo cotidiano, sin cifras nuevas.",
    )


def alertas(ctx: Contexto) -> Hechos:
    lista = _alertas(ctx)
    return Hechos(
        titulo=f"Lo que necesita tu atención · {ctx.periodo}",
        secciones=[("Alertas", [_linea_alerta(a) for a in lista] or ["🟢 No hay alertas: todo en orden."])],
        recomendaciones=[a.accion for a in lista if a.nivel != "verde"][:4],
        respaldo="Empieza por las alertas en rojo." if any(a.nivel == "rojo" for a in lista) else "Vas bien.",
        datos={"alertas": [a.model_dump() for a in lista]},
        sugerencias=["Hazme un análisis completo", "¿Qué se me va a agotar?"],
        enfoque="Prioriza las alertas: qué atender primero y por qué.",
    )


def financiamiento(ctx: Contexto) -> Hechos:
    k = servicio.kpis(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    proy = servicio.proyeccion(ctx.conn, ctx.id_empresa)
    lineas = _lineas_resultado(k)[-2:] + (_lineas_proyeccion(proy) if proy else [])
    rentable = k.utilidad > 0
    flujo_negativo = proy is not None and proy.saldo_proyectado < 0
    if rentable and flujo_negativo:
        respaldo = ("Eres rentable, pero tu efectivo viene justo. Puedes explorar un financiamiento de corto plazo para "
                    "capital de trabajo; compara costos y plazos antes de decidir.")
    elif not rentable:
        respaldo = ("Hoy tu negocio no está dejando ganancia. Antes de considerar un préstamo conviene corregir precios y "
                    "gastos, porque una deuda se paga con utilidades.")
    else:
        respaldo = "Tu negocio es rentable y tu efectivo alcanza: por ahora no parece necesario un financiamiento."
    return Hechos(
        titulo="¿Te conviene un financiamiento?",
        secciones=[("Lo que dicen tus números", lineas)],
        respaldo=respaldo,
        recomendaciones=["Si lo evalúas, compara el costo total (CAT), plazos y comisiones de varias opciones.",
                         "Pide solo lo que puedas pagar con la utilidad de tus meses flojos."],
        datos={"rentable": rentable, "flujo_negativo": flujo_negativo},
        sugerencias=["¿Me va a alcanzar el efectivo?", "¿En qué gasto más?"],
        aviso=True,
        enfoque="Presenta el financiamiento solo como opción a evaluar, nunca como instrucción. No menciones bancos.",
    )


def comparar(ctx: Contexto) -> Hechos:
    r = servicio.resumen(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    a, b, v = r.kpis, r.kpis_anterior, r.variaciones
    ant = r.periodo_anterior.etiqueta
    lineas = [
        f"Ventas: {dinero(a.ventas)} vs {dinero(b.ventas)} ({pct_cambio(v.ventas)})",
        f"Costo de mercancía: {dinero(a.costo_ventas)} vs {dinero(b.costo_ventas)} ({pct_cambio(v.costo_ventas)})",
        f"Gastos de operación: {dinero(a.gastos_operacion)} vs {dinero(b.gastos_operacion)} ({pct_cambio(v.gastos_operacion)})",
        f"Lo que ganaste: {dinero(a.utilidad)} vs {dinero(b.utilidad)} ({pct_cambio(v.utilidad)})",
        f"Margen: {pct(a.margen)} vs {pct(b.margen)}",
    ]
    return Hechos(
        titulo=f"{ctx.periodo} frente a {ant}", secciones=[(f"{ctx.periodo} vs {ant}", lineas)],
        respaldo=f"Tus ventas cambiaron {pct_cambio(v.ventas)} y lo que ganaste {pct_cambio(v.utilidad)} frente a {ant}.",
        datos={"actual": a.model_dump(), "anterior": b.model_dump()},
        sugerencias=["¿Por qué bajaron mis ventas?", "¿En qué gasto más?"],
        enfoque="Explica qué cambió más entre los dos periodos.",
    )


def analisis_completo(ctx: Contexto) -> Hechos:
    fz = servicio.finanzas(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    fl = servicio.flujo(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    p = _productos(ctx)
    k = servicio.kpis(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)
    lista = _alertas(ctx)
    pe = fz.punto_equilibrio
    fiscal = impuestos_srv.impuestos_del_periodo(ctx.conn, ctx.id_empresa, ctx.desde, ctx.hasta)

    costos = [f"Costo total de la mercancía vendida: **{dinero(k.costo_ventas)}**"]
    if len(fz.mensual) <= 12:
        costos += [f"{m.etiqueta}: {dinero(m.costo)}" for m in fz.mensual]
    gastos_l = [f"{g.categoria}: {dinero(g.monto)}" for g in fz.distribucion_gastos[:10]]
    gastos_l.append(f"**Total de gastos de operación: {dinero(k.gastos_operacion)}**")
    flujo_l = [f"Efectivo inicial: {dinero(fl.saldo_inicial)}", f"Entradas por ventas: {dinero(fl.entradas)}",
               f"Compras de mercancía: {dinero(fl.compras)}", f"Gastos: {dinero(fl.gastos)}",
               f"**Efectivo final: {dinero(fl.saldo_final)}**"]
    if fl.proyeccion:
        flujo_l.append(f"Proyección a 30 días: {dinero(fl.proyeccion.saldo_proyectado)}")
    inv = p.inventario
    criticos = [x for x in p.productos if x.semaforo == "rojo"]
    secciones = [
        ("Ingresos", [f"Ventas de productos: **{dinero(k.ventas)}**", "Otros ingresos: no registrados"]),
        ("Costos", costos),
        ("Gastos de operación", gastos_l),
        ("Utilidad", [f"Utilidad bruta: {dinero(k.utilidad_bruta)}",
                      f"Utilidad antes de impuestos: **{dinero(k.utilidad)}**",
                      f"Impuestos estimados (ISR {dinero(fiscal['isr'])} + IVA {dinero(fiscal['iva'])}): {dinero(fiscal['total'])}",
                      f"**Después de impuestos: {dinero(k.utilidad - fiscal['total'])}**"]),
        ("Margen", [f"Margen bruto: {pct(k.margen_bruto)}", f"Margen de utilidad: **{pct(k.margen)}**"]),
        ("Flujo de efectivo", flujo_l),
        ("Productos más rentables", [f"{x.nombre}: {dinero(x.utilidad)} de ganancia ({unidades(x.unidades, x.unidad)}, margen {pct(x.margen)})"
                                     for x in p.top_utilidad]),
        ("Productos con menor margen", [f"{x.nombre}: margen {pct(x.margen_actual)} (precio {dinero(x.precio_venta)}, costo {dinero(x.costo_promedio)})"
                                        for x in p.bajo_margen]),
        ("Inventario", [f"🟢 {inv.verde} bien · 🟡 {inv.amarillo} atención · 🔴 {inv.rojo} por agotarse",
                        f"Valor del inventario: {dinero(inv.valor_total)}"]
         + [f"🔴 {x.nombre}: quedan {unidades(x.stock_actual, x.unidad)} (~{numero(x.dias_inventario)} días)" for x in criticos[:5]]),
        ("Punto de equilibrio", [f"Necesitas vender {dinero(pe.punto_equilibrio_mensual)} al mes para no perder; "
                                 f"vendes en promedio {dinero(pe.ventas_mensuales_promedio)}"]),
        ("Riesgos y alertas", [_linea_alerta(a) for a in lista] or ["🟢 Sin alertas."]),
    ]
    para_llm = [
        f"Periodo: {ctx.periodo}", f"Ventas: {dinero(k.ventas)}", f"Lo que ganaste: {dinero(k.utilidad)}",
        f"Margen: {pct(k.margen)}", f"Efectivo final: {dinero(fl.saldo_final)}",
        f"Producto que más deja: {p.top_utilidad[0].nombre}" if p.top_utilidad else "",
        f"Producto con menor margen: {p.bajo_margen[0].nombre} ({pct(p.bajo_margen[0].margen_actual)})" if p.bajo_margen else "",
    ] + [f"Alerta {a.nivel}: {a.titulo}" for a in lista]
    estado = "ganó" if k.utilidad >= 0 else "perdió"
    return Hechos(
        titulo=f"Análisis financiero de {ctx.negocio} · {ctx.periodo}",
        secciones=secciones, para_llm=[x for x in para_llm if x],
        respaldo=f"En {ctx.periodo} tu negocio {estado} {dinero(abs(k.utilidad))} con un margen de {pct(k.margen)}. "
                 + (lista[0].mensaje if lista else ""),
        recomendaciones=list(dict.fromkeys(a.accion for a in lista if a.nivel != "verde"))[:5],
        datos={"kpis": k.model_dump(), "alertas": [a.id for a in lista]},
        sugerencias=["¿Qué se me va a agotar?", "¿Me va a alcanzar el efectivo?", "¿Debería pedir un préstamo?"],
        aviso=True,
        enfoque="Da un diagnóstico general en 3 o 4 oraciones: qué va bien, qué preocupa y qué hacer primero.",
        oraciones=4,
    )


CONSTRUCTORES = {
    "saludo": saludo, "importar": importar, "analisis_completo": analisis_completo,
    "ganancia": ganancia, "ventas": ventas, "productos_top": productos_top, "productos_bajo": productos_bajo,
    "inventario": inventario, "gastos": gastos, "flujo": flujo, "equilibrio": equilibrio, "alertas": alertas,
    "financiamiento": financiamiento, "comparar": comparar,
}

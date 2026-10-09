"""Asistente conversacional "Clara".

Flujo: pregunta → intención y periodo → hechos calculados por código → el LLM redacta una
interpretación corta usando solo esas cifras → guardia de cifras → respuesta en Markdown.
"""

from collections.abc import Iterator
from datetime import date

from pydantic import BaseModel
from sqlalchemy import Connection

from app.chat.hechos import AVISO, Contexto, Hechos
from app.chat.hechos_avanzados import CONSTRUCTORES
from app.chat.intenciones import detectar_periodo, intencion_por_llm, intencion_por_reglas
from app.finance import consultas as q
from app.finance.periodos import describir_periodo
from app.llm.guardia import cifras_permitidas, filtrar
from app.llm.ollama import get_llm

SISTEMA = """Eres Clara, la asistente financiera de "{negocio}" ({giro}), una tienda pequeña en México.
Le hablas de "tú" al dueño, en español de México, con tono cálido, claro y sin jerga contable.
Responde en {oraciones} oraciones como máximo, en un solo párrafo, sin listas ni títulos.
REGLAS ESTRICTAS:
- Usa SOLO las cifras de DATOS, copiadas exactamente (con $ y %). No hagas cálculos, no redondees, no inventes.
- Si te preguntan algo que no está en DATOS, dilo con honestidad.
- Nunca recomiendes bancos, instituciones ni productos financieros concretos. Un préstamo es solo una opción a evaluar.
- No repitas todas las cifras: interpreta lo importante y da un consejo práctico."""


class ChatRespuesta(BaseModel):
    answer: str
    intencion: str
    periodo: dict
    fuente: str             # "ollama" o "plantilla"
    sugerencias: list[str]
    datos: dict


def _contexto(conn: Connection, id_empresa: int, mensaje: str, desde: date | None, hasta: date | None,
              intencion_anterior: str | None) -> tuple[str, Contexto, bool]:
    emp = q.empresa(conn, id_empresa) or {}
    corte = q.rango_datos(conn, id_empresa)[1] or date.today()
    por_defecto = (desde, hasta) if desde and hasta else None
    periodo = detectar_periodo(mensaje, corte, por_defecto)
    intencion = intencion_por_reglas(mensaje)
    if intencion is None:
        # "¿y en agosto?" → misma intención que la pregunta anterior, con otro periodo.
        if intencion_anterior in CONSTRUCTORES and periodo.explicito:
            intencion = intencion_anterior
        else:
            # Mejor admitir que no sabe que contestar otra cosa (antes caía en "ganancia").
            intencion = intencion_por_llm(mensaje) or "fuera_de_alcance"
    if intencion == "analisis_completo" and not periodo.explicito:
        periodo.desde, periodo.hasta = date(corte.year, 1, 1), corte   # en lo que va del año
    ctx = Contexto(conn=conn, id_empresa=id_empresa, negocio=emp.get("nombre_negocio", "tu negocio"),
                   giro=emp.get("giro", ""), desde=periodo.desde, hasta=periodo.hasta, corte=corte,
                   mensaje=mensaje, periodo_explicito=periodo.explicito)
    return intencion, ctx, periodo.explicito


def _markdown_base(h: Hechos) -> str:
    partes = [f"### {h.titulo}"]
    for titulo, lineas in h.secciones:
        if lineas:
            partes.append(f"**{titulo}**\n" + "\n".join(f"- {linea}" for linea in lineas))
    return "\n\n".join(partes)


def _markdown_cierre(h: Hechos, narrativa: str) -> str:
    partes = []
    if narrativa:
        partes.append(f"**Lo que significa**\n\n{narrativa}")
    if h.recomendaciones:
        partes.append("**Recomendaciones**\n" + "\n".join(f"- {r}" for r in h.recomendaciones))
    if h.aviso:
        partes.append(f"> _{AVISO}_")
    return "\n\n".join(partes)


def _prompt(h: Hechos, ctx: Contexto, mensaje: str) -> tuple[str, str]:
    lineas = h.para_llm or [linea for _, ls in h.secciones for linea in ls]
    datos = "\n".join(f"- {linea.replace('**', '')}" for linea in lineas)
    sistema = SISTEMA.format(negocio=ctx.negocio, giro=ctx.giro, oraciones=h.oraciones)
    usuario = (f"PREGUNTA: {mensaje}\nPERIODO: {ctx.periodo}\nDATOS:\n{datos}\n"
               f"CONTEXTO: {h.respaldo}\nENFOQUE: {h.enfoque}")
    return sistema, usuario


def _limpiar(texto: str, h: Hechos, mensaje: str) -> str:
    permitidas = cifras_permitidas(h.secciones, h.para_llm, h.respaldo, h.recomendaciones, mensaje)
    limpio, _ = filtrar(texto.replace("**", ""), permitidas)
    return limpio if len(limpio) >= 30 else ""


def _respuesta(intencion: str, ctx: Contexto, h: Hechos, narrativa: str, fuente: str) -> ChatRespuesta:
    answer = "\n\n".join(p for p in (_markdown_base(h), _markdown_cierre(h, narrativa)) if p)
    return ChatRespuesta(
        answer=answer, intencion=intencion,
        periodo={"desde": ctx.desde.isoformat(), "hasta": ctx.hasta.isoformat(), "etiqueta": describir_periodo(ctx.desde, ctx.hasta)},
        fuente=fuente, sugerencias=h.sugerencias, datos=h.datos,
    )


def responder(conn: Connection, id_empresa: int, mensaje: str, desde: date | None = None, hasta: date | None = None,
              intencion_anterior: str | None = None) -> ChatRespuesta:
    intencion, ctx, _ = _contexto(conn, id_empresa, mensaje, desde, hasta, intencion_anterior)
    h = CONSTRUCTORES[intencion](ctx)
    narrativa, fuente = h.respaldo, "plantilla"
    if h.usa_llm:
        sistema, usuario = _prompt(h, ctx, mensaje)
        texto = get_llm().chat(sistema, usuario, temperatura=0.4, max_tokens=220)
        limpio = _limpiar(texto or "", h, mensaje)
        if limpio:
            narrativa, fuente = limpio, "ollama"
    return _respuesta(intencion, ctx, h, narrativa, fuente)


def responder_stream(conn: Connection, id_empresa: int, mensaje: str, desde: date | None = None,
                     hasta: date | None = None, intencion_anterior: str | None = None) -> Iterator[dict]:
    """Eventos: 'inicio' (cifras al instante) → 'token' (texto de la IA) → 'final' (respuesta validada)."""
    intencion, ctx, _ = _contexto(conn, id_empresa, mensaje, desde, hasta, intencion_anterior)
    h = CONSTRUCTORES[intencion](ctx)
    yield {"tipo": "inicio", "intencion": intencion, "base": _markdown_base(h)}
    narrativa, fuente = h.respaldo, "plantilla"
    if h.usa_llm:
        sistema, usuario = _prompt(h, ctx, mensaje)
        texto = ""
        for fragmento in get_llm().chat_stream(sistema, usuario, temperatura=0.4, max_tokens=220):
            texto += fragmento
            yield {"tipo": "token", "texto": fragmento}
        limpio = _limpiar(texto, h, mensaje)
        if limpio:
            narrativa, fuente = limpio, "ollama"
    yield {"tipo": "final", "respuesta": _respuesta(intencion, ctx, h, narrativa, fuente).model_dump()}

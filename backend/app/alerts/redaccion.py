"""Redacción de alertas con el LLM (Ollama).

El LLM recibe solo las métricas ya calculadas y formateadas, y devuelve un mensaje
por alerta. La guardia de cifras descarta cualquier oración con números inventados;
si no queda nada útil, se conserva el texto de la plantilla.
"""

import json

from app.alerts.reglas import Alerta
from app.llm.cache import CacheLLM, clave
from app.llm.guardia import cifras_permitidas, filtrar
from app.llm.ollama import get_llm

SISTEMA = """Eres el asistente financiero de una tienda pequeña en México.
Reescribe cada alerta como un aviso breve (máximo 2 oraciones), claro, cálido y accionable,
en español de México, hablándole de "tú" al dueño. Sin jerga contable.
REGLAS ESTRICTAS:
- Usa SOLO las cifras que vienen en "metricas", copiadas exactamente como están (con $ y %).
- No hagas cálculos, no redondees, no inventes cifras ni porcentajes.
- No recomiendes bancos, instituciones ni productos financieros concretos.
Responde SOLO un JSON: {"alertas": [{"id": "...", "mensaje": "..."}]}"""

_cache: CacheLLM[dict[str, str]] = CacheLLM()


def _clave(alertas: list[Alerta]) -> str:
    contenido = json.dumps([(a.id, a.metricas) for a in alertas], sort_keys=True, ensure_ascii=False)
    return clave(SISTEMA, contenido)


def _pedir_textos(alertas: list[Alerta]) -> dict[str, str] | None:
    entrada = [{"id": a.id, "nivel": a.nivel, "titulo": a.titulo, "metricas": a.metricas, "texto_base": a.mensaje}
               for a in alertas]
    crudo = get_llm().chat(SISTEMA, json.dumps({"alertas": entrada}, ensure_ascii=False),
                           formato_json=True, temperatura=0.3, max_tokens=900)
    if crudo is None:
        return None           # Ollama no respondió: no se guarda en caché, para reintentar
    textos: dict[str, str] = {}
    if crudo:
        try:
            for item in json.loads(crudo).get("alertas", []):
                if isinstance(item, dict) and isinstance(item.get("mensaje"), str):
                    textos[str(item.get("id"))] = item["mensaje"].strip()
        except (json.JSONDecodeError, AttributeError):
            textos = {}
    return textos             # vacío = respuesta inútil; se guarda para no volver a esperar al modelo


def redactar(alertas: list[Alerta]) -> list[Alerta]:
    if not alertas:
        return alertas
    textos = _cache.obtener(_clave(alertas), lambda: _pedir_textos(alertas))
    if not textos:
        return alertas          # sin IA: se quedan las plantillas
    resultado = []
    for a in alertas:
        texto = textos.get(a.id)
        if texto:
            limpio, _ = filtrar(texto, cifras_permitidas(a.metricas, a.mensaje))
            if len(limpio) >= 25:
                resultado.append(a.model_copy(update={"mensaje": limpio, "redactado_por_ia": True}))
                continue
        resultado.append(a)
    return resultado

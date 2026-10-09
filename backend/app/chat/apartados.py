"""Clara explica los apartados nuevos (proyecciones, impuestos, deudas).

Cada apartado arma un JSON con cifras YA calculadas y formateadas. Clara solo redacta: si su texto
trae un número que no está en el JSON, se descarta completo y se usa la plantilla determinista.
"""

import json

from app.llm.cache import CacheLLM, clave
from app.llm.guardia import cifras_permitidas, numeros
from app.llm.ollama import get_llm

SISTEMA = (
    "Eres Clara, asesora financiera de una pyme. Explica estos resultados en español sencillo, en máximo 5 frases, "
    "empezando por lo más urgente. Usa SOLO los números del JSON. No calcules ni inventes cifras. "
    "Si algo es estimado, dilo. No recomiendes bancos ni productos financieros concretos."
)
AVISO = "Orientación general, no constituye asesoría financiera, contable ni fiscal."


_cache: CacheLLM[str] = CacheLLM()


def _redactar(contenido: str) -> str | None:
    """Texto de Clara ya validado.

    None = Ollama no respondió (no se guarda: se reintenta después).
    "" = respondió, pero con una cifra inventada o algo inútil: se usa la plantilla, y se guarda esa
    decisión para no esperar otra vez al modelo por una respuesta que se volvería a descartar.
    """
    crudo = get_llm().chat(SISTEMA, contenido, temperatura=0.2, max_tokens=350)
    if crudo is None:
        return None
    texto = crudo.strip()
    if len(texto) < 25 or (numeros(texto) - cifras_permitidas(contenido)):
        return ""
    return texto


def explicar(datos: dict, plantilla: str) -> dict:
    """Devuelve {"texto", "redactado_por_ia", "aviso"}. `plantilla` es el texto de respaldo (sin IA)."""
    base = {"texto": plantilla, "redactado_por_ia": False, "aviso": AVISO}
    if not datos:
        return base
    contenido = json.dumps(datos, ensure_ascii=False, default=str)
    texto = _cache.obtener(clave(SISTEMA, contenido), lambda: _redactar(contenido))
    return {"texto": texto, "redactado_por_ia": True, "aviso": AVISO} if texto else base

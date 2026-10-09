"""Cliente mínimo de Ollama (LLM local) por HTTP.

Si Ollama no está corriendo o tarda demasiado, `chat` devuelve None y quien lo llame usa
su texto de respaldo (plantilla). La plataforma funciona completa sin IA.
Los logs nunca incluyen el contenido enviado (datos financieros sensibles, CLAUDE.md §8).
"""

import json
import logging
from collections.abc import Iterator
from functools import lru_cache

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


class ClienteOllama:
    def __init__(self, url: str, modelo: str, timeout: float, keep_alive: str = "30m"):
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.timeout = timeout
        # Cargar el modelo en memoria tarda varios segundos: se mantiene cargado entre peticiones.
        self.keep_alive = keep_alive

    def chat(self, sistema: str, usuario: str, *, formato_json: bool = False, temperatura: float = 0.3,
             max_tokens: int = 600) -> str | None:
        payload: dict = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperatura, "num_predict": max_tokens},
        }
        if formato_json:
            payload["format"] = "json"
        try:
            respuesta = httpx.post(f"{self.url}/api/chat", json=payload, timeout=self.timeout)
            respuesta.raise_for_status()
            return respuesta.json()["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, ValueError) as error:
            log.warning("Ollama no respondió (%s)", type(error).__name__)
            return None

    def chat_stream(self, sistema: str, usuario: str, *, temperatura: float = 0.3,
                    max_tokens: int = 300) -> Iterator[str]:
        """Genera el texto por fragmentos. Si Ollama falla, simplemente no produce nada."""
        payload = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperatura, "num_predict": max_tokens},
        }
        try:
            with httpx.stream("POST", f"{self.url}/api/chat", json=payload, timeout=self.timeout) as respuesta:
                respuesta.raise_for_status()
                for linea in respuesta.iter_lines():
                    if not linea:
                        continue
                    datos = json.loads(linea)
                    fragmento = datos.get("message", {}).get("content", "")
                    if fragmento:
                        yield fragmento
                    if datos.get("done"):
                        break
        except (httpx.HTTPError, ValueError) as error:
            log.warning("Ollama no respondió en streaming (%s)", type(error).__name__)

    def estado(self) -> dict:
        try:
            respuesta = httpx.get(f"{self.url}/api/tags", timeout=5)
            respuesta.raise_for_status()
            modelos = [m["name"] for m in respuesta.json().get("models", [])]
            return {"disponible": True, "modelo": self.modelo, "modelo_instalado": self.modelo in modelos}
        except (httpx.HTTPError, ValueError):
            return {"disponible": False, "modelo": self.modelo, "modelo_instalado": False}


@lru_cache
def get_llm() -> ClienteOllama:
    ajustes = get_settings()
    return ClienteOllama(ajustes.ollama_url, ajustes.ollama_modelo, ajustes.ollama_timeout, ajustes.ollama_keep_alive)

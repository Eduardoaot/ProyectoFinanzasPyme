"""Caché en memoria para textos redactados por el LLM.

El modelo local tarda de 10 a 30 s por respuesta y Ollama atiende una petición a la vez, así que
repetir la misma redacción (volver a abrir una página, o el doble pedido de React en desarrollo)
formaba una fila que hacía lenta toda la app. Aquí:
  - Misma entrada → misma respuesta, sin volver a llamar al modelo.
  - Si dos peticiones iguales llegan juntas, la segunda espera a la primera en vez de duplicarla.
  - Solo se guardan respuestas útiles: si el LLM falla, se reintenta la próxima vez.
  - Tamaño acotado: se descartan las entradas más viejas.
Las claves son hashes: el caché no guarda cifras en texto plano como llave.
"""

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")

_todos: list["CacheLLM"] = []


def clave(*partes: str) -> str:
    return hashlib.sha256("\x1f".join(partes).encode()).hexdigest()


class CacheLLM(Generic[T]):
    def __init__(self, maximo: int = 256, candados: int = 32):
        self._datos: OrderedDict[str, T] = OrderedDict()
        self._maximo = maximo
        self._global = threading.Lock()
        # Un candado por grupo de claves (no uno por clave): memoria fija y sin limpiar candados viejos.
        self._candados = [threading.Lock() for _ in range(candados)]
        _todos.append(self)

    def _leer(self, k: str) -> T | None:
        with self._global:
            if k in self._datos:
                self._datos.move_to_end(k)
                return self._datos[k]
            return None

    def obtener(self, k: str, calcular: Callable[[], T | None]) -> T | None:
        guardado = self._leer(k)
        if guardado is not None:
            return guardado
        with self._candados[int(k[:8], 16) % len(self._candados)]:
            guardado = self._leer(k)          # quizá otra petición igual lo calculó mientras esperábamos
            if guardado is not None:
                return guardado
            valor = calcular()
            if valor is not None:
                with self._global:
                    self._datos[k] = valor
                    while len(self._datos) > self._maximo:
                        self._datos.popitem(last=False)
            return valor

    def limpiar(self) -> None:
        with self._global:
            self._datos.clear()


def limpiar_todo() -> None:
    """Para pruebas: cada prueba arranca sin respuestas guardadas."""
    for c in _todos:
        c.limpiar()

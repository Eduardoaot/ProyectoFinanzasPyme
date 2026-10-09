"""Caché de textos del LLM: no repite llamadas, no guarda fallos y junta peticiones simultáneas."""

import threading
import time

from app.llm.cache import CacheLLM, clave


def test_misma_entrada_no_vuelve_a_llamar_al_llm():
    cache: CacheLLM[str] = CacheLLM()
    llamadas = []
    calcular = lambda: llamadas.append(1) or "texto"  # noqa: E731
    assert cache.obtener(clave("a"), calcular) == "texto"
    assert cache.obtener(clave("a"), calcular) == "texto"
    assert len(llamadas) == 1


def test_si_el_llm_falla_no_se_guarda_y_se_reintenta():
    cache: CacheLLM[str] = CacheLLM()
    respuestas = iter([None, "ya respondió"])
    assert cache.obtener(clave("b"), lambda: next(respuestas)) is None
    assert cache.obtener(clave("b"), lambda: next(respuestas)) == "ya respondió"


def test_tamano_acotado_descarta_lo_mas_viejo():
    cache: CacheLLM[str] = CacheLLM(maximo=2)
    for k in ("1", "2", "3"):
        cache.obtener(clave(k), lambda k=k: k)
    llamadas = []
    cache.obtener(clave("1"), lambda: llamadas.append(1) or "1")
    assert llamadas == [1]          # "1" se había descartado


def test_peticiones_iguales_simultaneas_llaman_una_sola_vez():
    cache: CacheLLM[str] = CacheLLM()
    llamadas = []

    def lento() -> str:
        llamadas.append(1)
        time.sleep(0.2)
        return "listo"

    resultados: list[str | None] = []
    hilos = [threading.Thread(target=lambda: resultados.append(cache.obtener(clave("c"), lento))) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados == ["listo"] * 4
    assert len(llamadas) == 1


class _LLMContado:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = 0

    def chat(self, *_, **__):
        self.llamadas += 1
        return self.respuesta


def test_explicacion_rechazada_por_la_guardia_no_se_vuelve_a_pedir(monkeypatch):
    from app.chat import apartados
    from app.llm.cache import limpiar_todo

    limpiar_todo()
    falso = _LLMContado("Este mes ganarías 999,999 pesos, mucho más de lo esperado por todos.")   # cifra inventada
    monkeypatch.setattr(apartados, "get_llm", lambda: falso)
    for _ in range(3):
        r = apartados.explicar({"utilidad": "$1,200"}, "Plantilla")
        assert r == {"texto": "Plantilla", "redactado_por_ia": False, "aviso": apartados.AVISO}
    assert falso.llamadas == 1


def test_si_ollama_no_responde_se_reintenta(monkeypatch):
    from app.chat import apartados
    from app.llm.cache import limpiar_todo

    limpiar_todo()
    falso = _LLMContado(None)
    monkeypatch.setattr(apartados, "get_llm", lambda: falso)
    apartados.explicar({"utilidad": "$1,200"}, "Plantilla")
    apartados.explicar({"utilidad": "$1,200"}, "Plantilla")
    assert falso.llamadas == 2

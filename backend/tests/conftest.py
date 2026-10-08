"""Base de datos SQLite en memoria con el dataset de demo completo, y un LLM falso.

Las pruebas no necesitan MySQL ni Ollama corriendo.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CARPETA_STAGING"] = os.path.join(os.path.dirname(__file__), ".staging_test")
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-longitud-suficiente-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import insert  # noqa: E402

from app.db import models as m  # noqa: E402
from app.db.session import crear_esquema, get_engine  # noqa: E402

PASSWORD = "Demo2026!"


class LLMFalso:
    """Simula Ollama. `respuesta` es lo que devolverá; None = Ollama apagado."""

    def __init__(self):
        self.respuesta: str | None = None
        self.llamadas = 0

    def chat(self, sistema, usuario, **_):
        self.llamadas += 1
        return self.respuesta

    def chat_stream(self, sistema, usuario, **_):
        self.llamadas += 1
        if self.respuesta:
            for palabra in self.respuesta.split(" "):
                yield palabra + " "

    def estado(self):
        return {"disponible": self.respuesta is not None, "modelo": "falso", "modelo_instalado": True}


@pytest.fixture(scope="session", autouse=True)
def base_de_datos():
    from scripts.generar_seed import construir

    engine = get_engine()
    crear_esquema(engine)
    filas = construir()
    with engine.begin() as conn:
        for tabla, registros in filas.items():
            for i in range(0, len(registros), 5000):
                conn.execute(insert(m.metadata.tables[tabla]), registros[i:i + 5000])
    yield engine


@pytest.fixture
def llm(monkeypatch):
    falso = LLMFalso()
    for modulo in ("app.llm.ollama", "app.chat.asistente", "app.chat.intenciones", "app.alerts.redaccion",
                   "app.ingestion.mapeo", "app.api.rutas_chat", "app.chat.apartados"):
        monkeypatch.setattr(f"{modulo}.get_llm", lambda: falso)
    return falso


@pytest.fixture
def cliente(llm):
    from app.main import app

    return TestClient(app)


def login(cliente: TestClient, email: str) -> dict:
    r = cliente.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ana(cliente):
    """Dueña de la Papelería (empresa 1)."""
    return login(cliente, "ana.ruiz@example.com")


@pytest.fixture
def lupita(cliente):
    """Dueña de Abarrotes (empresa 2)."""
    return login(cliente, "lupita.martinez@example.com")

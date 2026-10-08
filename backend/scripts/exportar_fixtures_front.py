"""Exporta respuestas reales de la API (datos de demostración) para las pruebas de interfaz del frontend.

Uso (desde backend/):  python -m scripts.exportar_fixtures_front
Escribe frontend/src/test/fixtures/predictivo.json con Proyecciones, Impuestos y Deudas de dos negocios.
"""

import json
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "secreto-solo-para-exportar-fixtures-0123456789"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import insert  # noqa: E402

from app.db import models as m  # noqa: E402
from app.db.session import crear_esquema, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.generar_seed import PASSWORD_DEMO, RAIZ, construir  # noqa: E402

RUTAS = {
    "proyecciones": "/proyecciones",
    "impuestos": "/impuestos",
    "gastos": "/impuestos/gastos",
    "deudas": "/deudas",
}
NEGOCIOS = {"papeleria": (1, "ana.ruiz@example.com"), "boutique": (3, "carlos.mendez@example.com")}


def main() -> None:
    engine = get_engine()
    crear_esquema(engine)
    with engine.begin() as conn:
        for tabla, filas in construir().items():
            for i in range(0, len(filas), 5000):
                conn.execute(insert(m.metadata.tables[tabla]), filas[i:i + 5000])
    cliente = TestClient(app)
    salida: dict = {}
    for clave, (id_empresa, email) in NEGOCIOS.items():
        token = cliente.post("/api/auth/login", json={"email": email, "password": PASSWORD_DEMO}).json()["token"]
        cabeceras = {"Authorization": f"Bearer {token}"}
        salida[clave] = {"id_empresa": id_empresa}
        for nombre, ruta in RUTAS.items():
            r = cliente.get(f"/api/empresas/{id_empresa}{ruta}", headers=cabeceras)
            r.raise_for_status()
            salida[clave][nombre] = r.json()
    destino = RAIZ / "frontend" / "src" / "test" / "fixtures"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "predictivo.json").write_text(json.dumps(salida, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Fixtures escritos en {destino / 'predictivo.json'}")


if __name__ == "__main__":
    main()

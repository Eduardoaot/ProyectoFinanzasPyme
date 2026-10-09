"""Invitar al contador: solo el dueño invita o quita acceso, y el invitado solo puede ver."""

from tests.conftest import login


def _registrar_contador(cliente, email: str) -> dict:
    r = cliente.post("/api/auth/registro", json={
        "nombre": "Rosa Contadora", "email": email, "password": "Contador2026!", "es_contador": True})
    assert r.status_code == 201, r.text
    assert r.json()["empresas"] == []          # sin negocio propio
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_registro_normal_sigue_pidiendo_negocio(cliente):
    r = cliente.post("/api/auth/registro", json={
        "nombre": "Sin Negocio", "email": "sin.negocio@example.com", "password": "Clave12345"})
    assert r.status_code == 422
    assert "negocio" in r.json()["detail"]


def test_dueno_invita_contador_que_solo_puede_ver_y_luego_le_quita_acceso(cliente, ana):
    rosa = _registrar_contador(cliente, "rosa.contadora@example.com")
    assert cliente.get("/api/empresas/1/resumen", headers=rosa).status_code == 404

    r = cliente.post("/api/empresas/1/accesos", headers=ana, json={"email": "Rosa.Contadora@example.com"})
    assert r.status_code == 201, r.text
    id_rosa = r.json()["id_usuario"]
    assert r.json()["rol"] == "consulta"

    # Ahora ve el negocio en su sesión, pero no puede cambiar nada ni invitar a otros.
    empresas = cliente.get("/api/auth/yo", headers=rosa).json()["empresas"]
    assert [(e["id_empresa"], e["rol"]) for e in empresas] == [(1, "consulta")]
    assert cliente.get("/api/empresas/1/resumen", headers=rosa).status_code == 200
    base = cliente.get("/api/empresas/1", headers=rosa).json()["umbrales"]
    assert cliente.put("/api/empresas/1/umbrales", headers=rosa, json=base).status_code == 403
    assert cliente.post("/api/empresas/1/accesos", headers=rosa, json={"email": "lupita.martinez@example.com"}).status_code == 403
    assert cliente.get("/api/empresas/1/accesos", headers=rosa).status_code == 403

    lista = cliente.get("/api/empresas/1/accesos", headers=ana).json()
    assert lista[0]["rol"] == "dueno" and lista[0]["eres_tu"] is True
    assert any(a["id_usuario"] == id_rosa and a["rol"] == "consulta" for a in lista)

    assert cliente.delete(f"/api/empresas/1/accesos/{id_rosa}", headers=ana).status_code == 204
    assert cliente.get("/api/empresas/1/resumen", headers=rosa).status_code == 404
    assert cliente.get("/api/auth/yo", headers=rosa).json()["empresas"] == []


def test_invitar_correo_sin_cuenta_o_repetido(cliente, ana):
    r = cliente.post("/api/empresas/1/accesos", headers=ana, json={"email": "nadie@example.com"})
    assert r.status_code == 404
    assert "registre" in r.json()["detail"]
    # Carlos ya tiene acceso de consulta a la papelería (semilla).
    assert cliente.post("/api/empresas/1/accesos", headers=ana, json={"email": "carlos.mendez@example.com"}).status_code == 409


def test_nadie_cambia_ni_quita_su_propio_acceso(cliente, ana):
    yo = cliente.get("/api/auth/yo", headers=ana).json()["usuario"]["id_usuario"]
    assert cliente.delete(f"/api/empresas/1/accesos/{yo}", headers=ana).status_code == 400
    assert cliente.patch(f"/api/empresas/1/accesos/{yo}", headers=ana, json={"rol": "consulta"}).status_code == 400


def test_dueno_vuelve_dueno_al_contador_y_lo_regresa_a_solo_ver(cliente, ana):
    memo = _registrar_contador(cliente, "memo.contador@example.com")
    id_memo = cliente.post("/api/empresas/1/accesos", headers=ana, json={"email": "memo.contador@example.com"}).json()["id_usuario"]
    base = cliente.get("/api/empresas/1", headers=memo).json()["umbrales"]
    assert cliente.put("/api/empresas/1/umbrales", headers=memo, json=base).status_code == 403

    r = cliente.patch(f"/api/empresas/1/accesos/{id_memo}", headers=ana, json={"rol": "dueno"})
    assert r.status_code == 200 and r.json()["rol"] == "dueno"
    assert cliente.put("/api/empresas/1/umbrales", headers=memo, json=base).status_code == 200
    assert cliente.get("/api/empresas/1/accesos", headers=memo).status_code == 200

    assert cliente.patch(f"/api/empresas/1/accesos/{id_memo}", headers=ana, json={"rol": "consulta"}).json()["rol"] == "consulta"
    assert cliente.put("/api/empresas/1/umbrales", headers=memo, json=base).status_code == 403
    assert cliente.patch(f"/api/empresas/1/accesos/{id_memo}", headers=ana, json={"rol": "jefe"}).status_code == 422
    assert cliente.delete(f"/api/empresas/1/accesos/{id_memo}", headers=ana).status_code == 204


def test_dueno_no_administra_accesos_de_otro_negocio(cliente, lupita):
    """Lupita es dueña de abarrotes, no de la papelería: ni ve ni cambia quién tiene acceso a ella."""
    carlos = login(cliente, "carlos.mendez@example.com")
    id_carlos = cliente.get("/api/auth/yo", headers=carlos).json()["usuario"]["id_usuario"]
    assert cliente.get("/api/empresas/1/accesos", headers=lupita).status_code == 404
    assert cliente.post("/api/empresas/1/accesos", headers=lupita, json={"email": "carlos.mendez@example.com"}).status_code == 404
    assert cliente.delete(f"/api/empresas/1/accesos/{id_carlos}", headers=lupita).status_code == 404


def test_perfil_cambia_nombre_y_contrasena(cliente):
    yo = _registrar_contador(cliente, "perfil.prueba@example.com")
    r = cliente.patch("/api/auth/yo", headers=yo, json={"nombre": "  Rosa Pérez  "})
    assert r.status_code == 200 and r.json()["nombre"] == "Rosa Pérez"
    assert cliente.get("/api/auth/yo", headers=yo).json()["usuario"]["nombre"] == "Rosa Pérez"

    mal = cliente.post("/api/auth/password", headers=yo, json={"actual": "otra-cosa", "nueva": "NuevaClave2026"})
    assert mal.status_code == 400 and "actual" in mal.json()["detail"]
    igual = cliente.post("/api/auth/password", headers=yo, json={"actual": "Contador2026!", "nueva": "Contador2026!"})
    assert igual.status_code == 400
    assert cliente.post("/api/auth/password", headers=yo, json={"actual": "Contador2026!", "nueva": "corta"}).status_code == 422
    assert cliente.post("/api/auth/password", headers=yo, json={"actual": "Contador2026!", "nueva": "NuevaClave2026"}).status_code == 204

    assert cliente.post("/api/auth/login", json={"email": "perfil.prueba@example.com", "password": "Contador2026!"}).status_code == 401
    assert cliente.post("/api/auth/login", json={"email": "perfil.prueba@example.com", "password": "NuevaClave2026"}).status_code == 200

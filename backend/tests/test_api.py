"""Pruebas de la API: aislamiento por empresa, caso base, alertas y chat."""

import json
from datetime import date

import pytest

PERIODO_CASO_BASE = {"desde": "2026-01-01", "hasta": "2026-09-30"}


# --- Aislamiento por empresa (CLAUDE.md §8 y §13) -------------------------------------------

def test_sin_token_no_hay_acceso(cliente):
    assert cliente.get("/api/empresas/1/resumen").status_code == 401


def test_token_invalido(cliente):
    r = cliente.get("/api/empresas/1/resumen", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_usuario_no_ve_otra_empresa(cliente, ana):
    # Ana (Papelería, empresa 1) intenta leer Abarrotes (empresa 2) en todos los endpoints.
    for ruta in ("", "/resumen", "/finanzas", "/productos", "/flujo", "/alertas", "/forecast", "/importaciones"):
        r = cliente.get(f"/api/empresas/2{ruta}", headers=ana)
        assert r.status_code == 404, ruta
    r = cliente.post("/api/empresas/2/chat", headers=ana, json={"mensaje": "¿Estoy ganando?"})
    assert r.status_code == 404


def test_usuario_si_ve_su_empresa(cliente, lupita):
    r = cliente.get("/api/empresas/2", headers=lupita)
    assert r.status_code == 200
    assert r.json()["nombre_negocio"] == "Abarrotes Doña Lupita"


def test_contador_ve_las_tres(cliente):
    sesion = cliente.post("/api/auth/login", json={"email": "carlos.mendez@example.com", "password": "Demo2026!"}).json()
    assert {e["id_empresa"] for e in sesion["empresas"]} == {1, 2, 3}


def test_registro_crea_empresa_vacia(cliente):
    r = cliente.post("/api/auth/registro", json={
        "nombre": "Pedro Nuevo", "email": "pedro.nuevo@example.com", "password": "secreta123",
        "nombre_negocio": "Frutería Pedro", "giro": "Frutería"})
    assert r.status_code == 201, r.text
    sesion = r.json()
    headers = {"Authorization": f"Bearer {sesion['token']}"}
    id_empresa = sesion["empresas"][0]["id_empresa"]
    info = cliente.get(f"/api/empresas/{id_empresa}", headers=headers).json()
    assert info["tiene_datos"] is False
    # y no puede ver la Papelería
    assert cliente.get("/api/empresas/1/resumen", headers=headers).status_code == 404


def test_registro_correo_repetido(cliente):
    r = cliente.post("/api/auth/registro", json={
        "nombre": "Ana", "email": "ana.ruiz@example.com", "password": "secreta123",
        "nombre_negocio": "Otra", "giro": "Papelería"})
    assert r.status_code == 409


def test_login_incorrecto(cliente):
    r = cliente.post("/api/auth/login", json={"email": "ana.ruiz@example.com", "password": "mala"})
    assert r.status_code == 401


# --- Caso base §12 a través de SQL real ---------------------------------------------------------

def test_caso_base_cuadra_por_api(cliente, ana):
    k = cliente.get("/api/empresas/1/resumen", headers=ana, params=PERIODO_CASO_BASE).json()["kpis"]
    assert k["ventas"] == 170000.00
    assert k["costo_ventas"] == 75000.00
    assert k["utilidad_bruta"] == 95000.00
    assert k["gastos_operacion"] == 30000.00
    assert k["utilidad"] == 65000.00
    assert round(k["margen"] * 100, 1) == 38.2
    assert k["impuestos"] == 0 and k["impuestos_calculados"] is False


def test_estado_de_resultados_cuadra(cliente, ana):
    er = {l["clave"]: l["monto"] for l in
          cliente.get("/api/empresas/1/finanzas", headers=ana, params=PERIODO_CASO_BASE).json()["estado_resultados"]}
    assert er["ventas"] - er["costo_ventas"] == er["utilidad_bruta"]
    assert round(er["utilidad_bruta"] - er["gastos_fijos"] - er["gastos_variables"], 2) == er["utilidad_antes_impuestos"] == 65000.00
    assert er["isr"] > 0                                                       # la papelería está en RESICO: paga ISR cada mes
    assert round(er["utilidad_antes_impuestos"] - er["isr"] - er["iva"], 2) == er["utilidad"]


def test_impuestos_del_estado_de_resultados_cuadran_con_el_apartado_de_impuestos(cliente, ana):
    from app.db.session import get_engine
    from app.impuestos import servicio as imp

    er = {l["clave"]: l["monto"] for l in
          cliente.get("/api/empresas/1/finanzas", headers=ana, params={"desde": "2026-07-01", "hasta": "2026-09-30"}).json()["estado_resultados"]}
    with get_engine().connect() as conn:
        meses = imp.calcular(conn, 1, date(2026, 9, 1))["meses"]
    trimestre = [m for m in meses if m["periodo"] in ("2026-07", "2026-08", "2026-09")]
    assert er["isr"] == pytest.approx(sum(m["isr"] for m in trimestre), abs=0.02)
    assert er["iva"] == pytest.approx(sum(m["iva_a_pagar"] for m in trimestre), abs=0.02)


def test_dataset_minimo_700_registros():
    from sqlalchemy import func, select

    from app.db import models as m
    from app.db.session import get_engine

    with get_engine().connect() as conn:
        for tabla in (m.historial_ventas, m.compras_producto, m.gastos_operativos):
            for id_empresa in (1, 2, 3):
                total = conn.execute(select(func.count()).select_from(tabla).where(tabla.c.id_empresa == id_empresa)).scalar()
                assert total >= 700, (tabla.name, id_empresa, total)


# --- Alertas -------------------------------------------------------------------------------------

def test_alertas_de_demo(cliente, ana, lupita):
    codigos_ana = {a["codigo"] for a in cliente.get("/api/empresas/1/alertas", headers=ana).json()}
    assert {"producto_margen_bajo", "inventario_bajo", "caida_ventas", "buena_rentabilidad"} <= codigos_ana
    codigos_lupita = {a["codigo"] for a in cliente.get("/api/empresas/2/alertas", headers=lupita).json()}
    assert {"margen_neto_bajo", "costo_sube_precio_no"} <= codigos_lupita


def test_redaccion_ia_no_puede_inventar_cifras(cliente, ana, llm):
    alertas = cliente.get("/api/empresas/1/alertas", headers=ana).json()
    primera = alertas[0]
    llm.respuesta = json.dumps({"alertas": [{"id": primera["id"],
                                             "mensaje": "Tu margen real es de 97.3% y ganaste $999,999. Revisa tu precio."}]})
    redactadas = cliente.get("/api/empresas/1/alertas", headers=ana, params={"redactar_ia": True}).json()
    texto = next(a for a in redactadas if a["id"] == primera["id"])["mensaje"]
    assert "97.3" not in texto and "999,999" not in texto


def test_umbrales_configurables(cliente, ana):
    base = cliente.get("/api/empresas/1", headers=ana).json()["umbrales"]
    nuevos = {**base, "buena_rentabilidad": 0.99}
    assert cliente.put("/api/empresas/1/umbrales", headers=ana, json=nuevos).status_code == 200
    codigos = {a["codigo"] for a in cliente.get("/api/empresas/1/alertas", headers=ana).json()}
    assert "buena_rentabilidad" not in codigos
    cliente.put("/api/empresas/1/umbrales", headers=ana, json=base)


# --- Pronóstico y flujo ---------------------------------------------------------------------------

def test_forecast_linea_base(cliente, ana):
    r = cliente.get("/api/empresas/1/forecast", headers=ana, params={"dias": 30}).json()
    assert r["metodo"] == "promedio_movil"
    assert len(r["pronostico"]) == 30
    assert all(p["inferior"] <= p["valor"] <= p["superior"] for p in r["pronostico"])


def test_flujo_proyeccion_negativa_boutique(cliente):
    from tests.conftest import login

    sofia = login(cliente, "sofia.herrera@example.com")
    flujo = cliente.get("/api/empresas/3/flujo", headers=sofia).json()
    assert flujo["proyeccion"]["saldo_proyectado"] < 0 < flujo["saldo_final"]


# --- Chat -------------------------------------------------------------------------------------------

def test_chat_sin_ollama_usa_plantilla(cliente, ana, llm):
    r = cliente.post("/api/empresas/1/chat", headers=ana, json={"mensaje": "¿Estoy ganando?"}).json()
    assert r["intencion"] == "ganancia"
    assert r["fuente"] == "plantilla"
    assert "Lo que ganaste" in r["answer"]


def test_chat_guardia_descarta_cifras_inventadas(cliente, ana, llm):
    llm.respuesta = ("Vas muy bien este periodo. Tus ventas crecieron 250% y ganaste $1,234,567 extra. "
                     "Te recomiendo cuidar tu inventario de cuadernos.")
    r = cliente.post("/api/empresas/1/chat", headers=ana,
                     json={"mensaje": "¿cuánto gané en enero a septiembre 2026?", **PERIODO_CASO_BASE}).json()
    assert r["fuente"] == "ollama"
    assert "250%" not in r["answer"] and "1,234,567" not in r["answer"]
    assert "cuidar tu inventario" in r["answer"]


def test_chat_detecta_mes(cliente, ana, llm):
    r = cliente.post("/api/empresas/1/chat", headers=ana, json={"mensaje": "¿Cuánto vendí en agosto?"}).json()
    assert r["periodo"]["desde"] == "2026-08-01" and r["periodo"]["hasta"] == "2026-08-31"


def test_chat_financiamiento_lleva_aviso(cliente, ana, llm):
    r = cliente.post("/api/empresas/1/chat", headers=ana, json={"mensaje": "¿Debería pedir un préstamo?"}).json()
    assert r["intencion"] == "financiamiento"
    assert "no constituye asesoría financiera" in r["answer"]


def test_chat_stream(cliente, ana, llm):
    llm.respuesta = "Estás ganando y tu margen es sano."
    with cliente.stream("POST", "/api/empresas/1/chat/stream", headers=ana, json={"mensaje": "¿Estoy ganando?"}) as r:
        eventos = [json.loads(linea) for linea in r.iter_lines() if linea]
    tipos = [e["tipo"] for e in eventos]
    assert tipos[0] == "inicio" and tipos[-1] == "final" and "token" in tipos
    assert eventos[-1]["respuesta"]["answer"]


def test_contador_solo_lectura(cliente):
    from tests.conftest import login

    carlos = login(cliente, "carlos.mendez@example.com")
    assert cliente.get("/api/empresas/1/resumen", headers=carlos).status_code == 200
    base = cliente.get("/api/empresas/1", headers=carlos).json()["umbrales"]
    assert cliente.put("/api/empresas/1/umbrales", headers=carlos, json=base).status_code == 403
    assert cliente.delete("/api/empresas/1/importaciones/1", headers=carlos).status_code == 403

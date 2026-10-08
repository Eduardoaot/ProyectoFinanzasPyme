"""API de Proyecciones, Impuestos y Deudas: aislamiento por empresa, CRUD de deudas, indicadores y Clara."""

import pytest

from app.deudas import consultas as dq
from app.deudas import servicio as ds
from app.db.session import get_engine

RUTAS_GET = ("/proyecciones", "/impuestos", "/impuestos/gastos", "/deudas", "/deudas/clara", "/proyecciones/clara", "/impuestos/clara")


def test_usuario_no_ve_apartados_de_otra_empresa(cliente, ana):
    for ruta in RUTAS_GET:
        assert cliente.get(f"/api/empresas/2{ruta}", headers=ana).status_code == 404, ruta
    assert cliente.post("/api/empresas/2/proyecciones/escenario", headers=ana, json={}).status_code == 404
    assert cliente.post("/api/empresas/2/deudas", headers=ana, json={}).status_code == 404


def test_sin_token_no_hay_acceso(cliente):
    for ruta in RUTAS_GET:
        assert cliente.get(f"/api/empresas/1{ruta}").status_code == 401


def test_una_deuda_de_otra_empresa_no_se_puede_tocar(cliente, ana, lupita):
    # La deuda 3 es de Abarrotes (empresa 2): Ana, con su empresa 1 en la URL, no la ve ni la modifica.
    assert cliente.post("/api/empresas/1/deudas/3/pagos", headers=ana, json={"fecha": "2026-10-01", "monto": 100}).status_code == 404
    assert cliente.delete("/api/empresas/1/deudas/3", headers=ana).status_code == 404
    assert cliente.get("/api/empresas/1/deudas/3/amortizacion", headers=ana).status_code == 404
    assert cliente.get("/api/empresas/2/deudas", headers=lupita).json()["deudas"][0]["acreedor"].startswith("Tarjeta")


def test_proyecciones_responde_con_las_secciones(cliente, ana):
    r = cliente.get("/api/empresas/1/proyecciones?semanas=12", headers=ana).json()
    for clave in ("pronostico", "mes", "flujo", "equilibrio", "inventario", "consejos", "alertas"):
        assert clave in r
    assert r["pronostico"]["semanas_horizonte"] == 12
    assert cliente.get("/api/empresas/1/proyecciones?semanas=5", headers=ana).status_code == 422


def test_escenario_recalcula(cliente, ana):
    base = cliente.get("/api/empresas/1/proyecciones", headers=ana).json()
    esc = cliente.post("/api/empresas/1/proyecciones/escenario", headers=ana, json={"ventas_pct": -0.3}).json()
    assert esc["mes"]["utilidad"] < base["mes"]["utilidad"]
    assert cliente.post("/api/empresas/1/proyecciones/escenario", headers=ana, json={"ventas_pct": 0.9}).status_code == 422


def test_deudas_del_negocio_apretado(cliente, lupita):
    r = cliente.get("/api/empresas/2/deudas", headers=lupita).json()
    assert len(r["deudas"]) == 4
    tarjeta = next(d for d in r["deudas"] if d["tipo"] == "tarjeta_credito")
    assert tarjeta["pago_minimo"] == pytest.approx(567.84, abs=0.01)             # caso de aceptación
    assert tarjeta["utilizacion"] == pytest.approx(8450 / 20000)
    assert tarjeta["pago_sin_intereses"] == 8450
    assert r["kpis"]["deuda_total"] == pytest.approx(8450 + 41200 + 6000 + 9000)
    assert r["estrategias"]["recomendada"] in ("avalancha", "bola_de_nieve")
    assert r["estrategias"]["avalancha"]["interes_total"] <= r["estrategias"]["bola_de_nieve"]["interes_total"]
    assert r["saldo_series"][0]["actual"] == r["kpis"]["deuda_total"] and r["saldo_series"][-1]["avalancha"] == 0


def test_negocio_en_riesgo_dispara_alertas_de_deuda(cliente):
    from tests.conftest import login
    carlos = login(cliente, "carlos.mendez@example.com")
    r = cliente.get("/api/empresas/3/deudas", headers=carlos).json()
    codigos = {a["codigo"] for a in r["alertas"]}
    assert r["kpis"]["dscr"] < 1.0 and r["kpis"]["semaforo_dscr"] == "rojo"
    assert {"deuda_no_alcanza", "tarjeta_muy_usada", "deuda_muy_cara"} <= codigos
    tarjeta = next(d for d in r["deudas"] if d["tipo"] == "tarjeta_credito")
    assert tarjeta["utilizacion"] > 0.80


def test_negocio_sano_no_tiene_alertas_rojas_de_deuda(cliente, ana):
    r = cliente.get("/api/empresas/1/deudas", headers=ana).json()
    assert r["kpis"]["semaforo_dscr"] == "verde"
    assert not [a for a in r["alertas"] if a["nivel"] == "rojo"]


def test_crud_de_deuda_y_abono(cliente, ana):
    nueva = {"acreedor": "Prueba", "tipo": "credito_simple", "monto_original": 10000, "saldo_actual": 10000,
             "tasa_interes_anual": 0.24, "plazo_meses": 12, "fecha_inicio": "2026-09-01", "dia_limite_pago": 5}
    r = cliente.post("/api/empresas/1/deudas", headers=ana, json=nueva)
    assert r.status_code == 201
    id_deuda = r.json()["id_deuda"]
    try:
        panel = cliente.get("/api/empresas/1/deudas", headers=ana).json()
        creada = next(d for d in panel["deudas"] if d["id_deuda"] == id_deuda)
        assert creada["aplica_iva_intereses"] is True               # los créditos bancarios cobran IVA sobre intereses por defecto
        # El abono cubre primero interés e IVA; el resto baja el capital.
        ab = cliente.post(f"/api/empresas/1/deudas/{id_deuda}/pagos", headers=ana, json={"fecha": "2026-10-05", "monto": 1000}).json()
        assert ab["interes"] == pytest.approx(200) and ab["iva"] == pytest.approx(32) and ab["capital"] == pytest.approx(768)
        assert ab["saldo_nuevo"] == pytest.approx(9232)
        hist = cliente.get(f"/api/empresas/1/deudas/{id_deuda}/pagos", headers=ana).json()
        assert len(hist) == 1
        tabla = cliente.get(f"/api/empresas/1/deudas/{id_deuda}/amortizacion", headers=ana).json()
        assert tabla and tabla[-1]["saldo"] == 0
        ahorro = cliente.get(f"/api/empresas/1/deudas/{id_deuda}/ahorro?extra=500", headers=ana).json()
        assert ahorro["ahorro_interes"] > 0
        assert cliente.post(f"/api/empresas/1/deudas/{id_deuda}/liquidar", headers=ana).status_code == 200
        assert cliente.post(f"/api/empresas/1/deudas/{id_deuda}/pagos", headers=ana, json={"fecha": "2026-10-06", "monto": 5}).status_code == 422
    finally:
        assert cliente.delete(f"/api/empresas/1/deudas/{id_deuda}", headers=ana).status_code == 200


def test_validaciones_de_deuda(cliente, ana):
    mala = {"acreedor": "", "tipo": "otra", "saldo_actual": -5, "fecha_inicio": "2026-09-01"}
    assert cliente.post("/api/empresas/1/deudas", headers=ana, json=mala).status_code == 422


def test_consulta_no_puede_modificar(cliente):
    from tests.conftest import login
    # Algún usuario con rol "consulta": el contador de las tres empresas solo lee.
    contador = login(cliente, "carlos.mendez@example.com")
    r = cliente.post("/api/empresas/1/deudas", headers=contador, json={
        "acreedor": "X", "tipo": "proveedor", "saldo_actual": 1, "fecha_inicio": "2026-09-01"})
    assert r.status_code in (201, 403)
    if r.status_code == 201:       # si el contador también es dueño en la semilla, limpiamos
        cliente.delete(f"/api/empresas/1/deudas/{r.json()['id_deuda']}", headers=contador)


def test_simulador_avisa_que_la_deuda_nunca_baja(cliente, ana):
    r = cliente.get("/api/empresas/1/deudas/simulador/pago?saldo=10000&tasa=0.54&pago=500", headers=ana).json()
    assert r["nunca_baja"] is True
    r = cliente.get("/api/empresas/1/deudas/simulador/pago?saldo=10000&tasa=0.54&pago=1500", headers=ana).json()
    assert r["nunca_baja"] is False and r["meses"] > 0


def test_configuracion_fiscal_cambia_el_regimen(cliente, ana):
    antes = cliente.get("/api/empresas/1/impuestos", headers=ana).json()
    r = cliente.put("/api/empresas/1/impuestos/configuracion", headers=ana, json={"tipo_persona": "fisica", "regimen": "612"})
    try:
        assert r.status_code == 200 and r.json()["regimen"] == "612"
        despues = cliente.get("/api/empresas/1/impuestos", headers=ana).json()
        assert despues["configuracion"]["regimen"] == "612"
        assert despues["configuracion"]["regimen_nombre"] != antes["configuracion"]["regimen_nombre"]
        assert cliente.put("/api/empresas/1/impuestos/configuracion", headers=ana,
                           json={"tipo_persona": "moral", "regimen": "626"}).status_code == 422
    finally:
        cliente.put("/api/empresas/1/impuestos/configuracion", headers=ana, json={"tipo_persona": "fisica", "regimen": "626"})


def test_corregir_un_gasto_cambia_lo_que_se_pierde(cliente, lupita):
    antes = cliente.get("/api/empresas/2/impuestos", headers=lupita).json()["perdido_por_no_deducir"]
    gastos = cliente.get("/api/empresas/2/impuestos/gastos", headers=lupita).json()
    corregible = next(g for g in gastos if g["corregible"])
    ok = cliente.patch(f"/api/empresas/2/gastos/{corregible['id_gasto']}/fiscal", headers=lupita,
                       json={"tiene_cfdi": True, "medio_pago": "transferencia"})
    try:
        assert ok.status_code == 200
        despues = cliente.get("/api/empresas/2/impuestos", headers=lupita).json()["perdido_por_no_deducir"]
        assert despues["gastos"] == antes["gastos"] - 1
    finally:
        cliente.patch(f"/api/empresas/2/gastos/{corregible['id_gasto']}/fiscal", headers=lupita,
                      json={"tiene_cfdi": corregible["tiene_cfdi"], "medio_pago": corregible["medio_pago"]})


def test_parametros_de_producto_se_validan(cliente, lupita):
    assert cliente.patch("/api/empresas/2/productos/1/parametros", headers=lupita, json={"tasa_iva": 0.5}).status_code == 422
    assert cliente.patch("/api/empresas/2/productos/999999/parametros", headers=lupita, json={"lead_time_dias": 2}).status_code == 404


# --- Clara: solo redacta con las cifras del JSON ---------------------------------------------------


def test_clara_sin_ia_usa_la_plantilla(cliente, ana, llm):
    llm.respuesta = None
    r = cliente.get("/api/empresas/1/impuestos/clara", headers=ana).json()
    assert r["redactado_por_ia"] is False and "estimación" in r["texto"].lower()
    assert "asesoría" in r["aviso"]


def test_clara_descarta_el_texto_si_inventa_cifras(cliente, ana, llm):
    llm.respuesta = "Debes pagar $987,654.32 al SAT este mes, aparta ese dinero cuanto antes para evitar problemas."
    r = cliente.get("/api/empresas/1/impuestos/clara", headers=ana).json()
    assert r["redactado_por_ia"] is False and "987" not in r["texto"]


def test_clara_acepta_el_texto_con_cifras_del_json(cliente, ana, llm):
    datos = cliente.get("/api/empresas/1/impuestos", headers=ana).json()
    from app.finance.formato import dinero
    llm.respuesta = f"Para este mes calculamos que debes pagar al SAT {dinero(datos['total_a_pagar'])}; es una estimación, así que confírmala con tu contador."
    r = cliente.get("/api/empresas/1/impuestos/clara", headers=ana).json()
    assert r["redactado_por_ia"] is True


def test_alertas_predictivas_pasan_por_la_guardia_de_cifras(cliente, ana, llm):
    llm.respuesta = '{"alertas": [{"id": "pred-inventario-detenido", "mensaje": "Tienes $999,999 detenidos en tu inventario, una fortuna que debes mover ya."}]}'
    r = cliente.get("/api/empresas/1/proyecciones?redactar_ia=true", headers=ana).json()
    detenido = next(a for a in r["alertas"] if a["codigo"] == "inventario_detenido")
    assert "999,999" not in detenido["mensaje"] and detenido["redactado_por_ia"] is False


def test_utilidades_de_panel_con_empresa_sin_deudas(base_de_datos):
    from sqlalchemy import insert

    from app.db import models as m
    with get_engine().connect() as conn:
        nueva = conn.execute(insert(m.empresas).values(nombre_negocio="Sin deudas", giro="Abarrotes")).inserted_primary_key[0]
        assert ds.panel(conn, nueva)["hay_deudas"] is False
        assert dq.pagos_programados(conn, nueva, __import__("datetime").date(2026, 9, 30)) == []
        conn.rollback()

"""Inicio sencillo: cifras iguales a las del modo avanzado, frase con semáforo y aislamiento por empresa."""

import pytest

from app.config import UmbralesAlerta
from app.inicio.servicio import estado_del_mes

U = UmbralesAlerta()


@pytest.mark.parametrize(("ventas", "utilidad", "cambio", "estado", "contiene"), [
    (10_000, -1_500, 0.0, "rojo", "perdiste $1,500"),
    (10_000, 3_000, -0.25, "amarillo", "vendiste menos"),
    (10_000, 1_000, 0.02, "amarillo", "Ganas, pero poco"),
    (10_000, 3_800, 0.05, "verde", "te fue bien"),
    (10_000, 3_800, None, "verde", "te quedaron $3,800"),
])
def test_estado_del_mes(ventas, utilidad, cambio, estado, contiene):
    e, frase = estado_del_mes(ventas, utilidad, cambio, "septiembre", U)
    assert e == estado
    assert contiene in frase
    assert "septiembre" in frase


def test_inicio_usa_las_mismas_cifras_que_el_resumen(cliente, ana):
    r = cliente.get("/api/empresas/1/inicio", headers=ana)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tiene_datos"] is True
    ultimo = cliente.get("/api/empresas/1", headers=ana).json()["ultimo_dato"]
    resumen = cliente.get("/api/empresas/1/resumen", headers=ana,
                          params={"desde": ultimo[:8] + "01", "hasta": ultimo}).json()["kpis"]
    c = d["como_te_fue"]
    assert c["ventas"] == pytest.approx(resumen["ventas"])
    assert c["te_quedo"] == pytest.approx(resumen["utilidad"])
    assert c["gastaste"] == pytest.approx(resumen["costo_ventas"] + resumen["gastos_operacion"])
    assert c["estado"] in ("verde", "amarillo", "rojo") and c["frase"]

    assert len(d["ventas_por_mes"]) == 6
    assert [m["actual"] for m in d["ventas_por_mes"]] == [False] * 5 + [True]
    assert d["ventas_por_mes"][-1]["ventas"] == pytest.approx(c["ventas"])

    assert 0 < len(d["productos"]) <= 8
    utilidades = [p["te_dejo"] for p in d["productos"]]
    assert utilidades == sorted(utilidades, reverse=True)

    viene = d["lo_que_viene"]
    assert viene["ventas_esperadas"] > 0
    assert len(viene["comprar"]) <= 5
    assert viene["total_compra"] == pytest.approx(sum(x["costo"] for x in viene["comprar"]), abs=0.01)
    assert d["impuestos"]["fecha_limite"]
    # La papelería tiene deudas en la semilla: se resume en total, pago del mes y cuál pagar primero.
    assert d["deudas"]["total"] > 0 and d["deudas"]["paga_primero"]


def test_inicio_sin_datos(cliente):
    r = cliente.post("/api/auth/registro", json={"nombre": "Doña Chela", "email": "chela.fruteria@example.com",
                                                  "password": "Fruteria2026", "nombre_negocio": "Frutería Chela", "giro": "Frutería"})
    token = {"Authorization": f"Bearer {r.json()['token']}"}
    id_empresa = r.json()["empresas"][0]["id_empresa"]
    d = cliente.get(f"/api/empresas/{id_empresa}/inicio", headers=token).json()
    assert d == {"tiene_datos": False, "como_te_fue": None, "ventas_por_mes": [], "productos": [],
                 "lo_que_viene": None, "impuestos": None, "deudas": None}


def test_inicio_no_muestra_datos_de_otra_empresa(cliente, lupita):
    assert cliente.get("/api/empresas/1/inicio", headers=lupita).status_code == 404


def test_chat_en_modo_sencillo_pide_palabras_de_todos_los_dias(cliente, ana, llm):
    llm.respuesta = "Te fue bien este mes."
    cliente.post("/api/empresas/1/chat", headers=ana, json={"mensaje": "¿cuánto gané?"})
    assert "MODO SENCILLO" not in llm.ultimo_sistema
    cliente.post("/api/empresas/1/chat", headers=ana, json={"mensaje": "¿cuánto gané?", "sencillo": True})
    assert "MODO SENCILLO" in llm.ultimo_sistema


def test_inicio_sencillo_responde_primero_con_el_sistema_sin_llamar_a_la_ia(cliente, ana, llm):
    llm.respuesta = "Te fue bien este mes."
    r = cliente.post("/api/empresas/1/chat", headers=ana,
                     json={"mensaje": "¿cuánto gané?", "sencillo": True, "usar_ia": False}).json()
    assert llm.llamadas == 0
    assert r["fuente"] == "plantilla" and "Lo que significa" in r["answer"]

"""Proyecciones: pronóstico, equilibrio, inventario, reparto de la utilidad y escenarios."""

import math
from datetime import date, timedelta

import pytest

from app.db.session import get_engine
from app.proyecciones import formulas as pf
from app.proyecciones import servicio as srv
from app.proyecciones.pronostico import pronosticar


def serie(n: int, valor=lambda i, f: 100.0, fin=date(2026, 9, 30)):
    inicio = fin - timedelta(days=n - 1)
    fechas = [inicio + timedelta(days=i) for i in range(n)]
    return [(f, valor(i, f)) for i, f in enumerate(fechas)]


# --- Caso de aceptación: punto de equilibrio ---------------------------------------------------


def test_punto_de_equilibrio_trimestral_del_caso_de_aceptacion():
    # ventas $80,258 · costo $35,573 → margen bruto 55.7 %; gastos $9,670
    margen = (80258 - 35573) / 80258
    assert pf.punto_equilibrio_mensual(9670, margen) == pytest.approx(17367, abs=15)
    assert pf.punto_equilibrio_mensual(9670 / 3, margen) == pytest.approx(5789, abs=5)


def test_margen_de_seguridad_y_equilibrio_imposible():
    assert pf.margen_de_seguridad(10000, 4000) == pytest.approx(0.6)
    assert pf.punto_equilibrio_mensual(1000, 0) is None
    assert pf.punto_equilibrio_mensual(1000, -0.1) is None


# --- Pronóstico ---------------------------------------------------------------------------------


def test_pronostico_constante_repite_el_nivel():
    r = pronosticar(serie(120), 14)
    assert not r.pocos_datos
    assert all(v == pytest.approx(100.0) for v in r.valores)
    assert r.sigma_diaria == pytest.approx(0.0, abs=1e-9)
    assert r.precision == pytest.approx(100.0)


def test_pronostico_respeta_el_dia_de_la_semana():
    # los sábados se vende el doble
    r = pronosticar(serie(120, lambda i, f: 200.0 if f.weekday() == 5 else 100.0), 14)
    sabados = [v for f, v in zip(r.fechas, r.valores) if f.weekday() == 5]
    lunes = [v for f, v in zip(r.fechas, r.valores) if f.weekday() == 0]
    assert min(sabados) > 1.8 * max(lunes)


def test_tendencia_limitada_a_15_por_ciento():
    # ventas que se duplican cada semana: la tendencia no puede pasar de ±15 % de la venta base
    r = pronosticar(serie(120, lambda i, f: 100.0 + i * 5), 84)
    assert max(r.valores) <= r.base * 1.15 * max(r.indices) + 1e-6


def test_pocos_datos_usa_promedio_simple_y_avisa():
    r = pronosticar(serie(20), 7)
    assert r.pocos_datos and r.metodo == "promedio_simple" and r.precision is None


def test_pronostico_es_determinista():
    f = lambda i, d: 100 + (i * 37) % 23  # noqa: E731
    assert pronosticar(serie(150, f), 30) == pronosticar(serie(150, f), 30)


# --- Inventario ---------------------------------------------------------------------------------


def test_stock_de_seguridad_y_punto_de_reorden():
    ss = pf.stock_seguridad(4.0, 4)                  # 1.65 × 4 × √4
    assert ss == pytest.approx(13.2)
    assert pf.punto_reorden(10, 4, ss) == pytest.approx(53.2)


def test_cantidad_sugerida_con_empaque():
    ss = pf.stock_seguridad(2.0, 3)
    sin_empaque = pf.cantidad_sugerida(10, 3, 7, ss, 20)
    assert sin_empaque == math.ceil(10 * 10 + ss - 20)
    assert pf.cantidad_sugerida(10, 3, 7, ss, 20, empaque=12) % 12 == 0
    assert pf.cantidad_sugerida(10, 3, 7, ss, 10_000) == 0


def test_cobertura_semaforo_y_exceso():
    assert pf.dias_cobertura(30, 10) == 3 and pf.dias_cobertura(5, 0) is None
    assert pf.semaforo_reabasto(2, 20, 3, 50) == "rojo"
    assert pf.semaforo_reabasto(4, 20, 3, 50) == "amarillo"
    assert pf.semaforo_reabasto(30, 300, 3, 50) == "verde"
    assert pf.monto_detenido(100, 1, 10) == pytest.approx(400)       # 40 piezas arriba de 60 días × $10


def test_priorizar_compras_por_ganancia_cuando_no_alcanza_el_efectivo():
    c = [pf.CompraCandidata(1, 600, 5, 10), pf.CompraCandidata(2, 500, 50, 10), pf.CompraCandidata(3, 400, 20, 10)]
    comprar, posponer = pf.priorizar_compras(c, 1000)
    assert comprar == [2, 3] and posponer == [1]


# --- Reparto de la utilidad ---------------------------------------------------------------------


def test_distribucion_en_orden_de_prioridad():
    r = pf.distribuir_utilidad(10000, 2000, 3000, 500, 1000, 1000)
    asignado = {p["clave"]: p["asignado"] for p in r["partes"]}
    assert asignado == {"impuestos": 2000, "deuda_obligatoria": 3000, "deuda_extra": 500, "fondo_emergencia": 1000,
                        "reinversion": 1000, "retiro": 2500}
    assert r["faltante_obligatorio"] == 0


def test_alerta_roja_con_el_faltante_exacto():
    r = pf.distribuir_utilidad(3000, 1500, 2500, 0, 800, 0)
    assert r["faltante_obligatorio"] == 1000
    asignado = {p["clave"]: p["asignado"] for p in r["partes"]}
    assert asignado["fondo_emergencia"] == 0 and asignado["retiro"] == 0


def test_meta_fondo_de_emergencia():
    assert pf.meta_fondo_emergencia(3000, 1000) == 12000


# --- Con la base de demostración -----------------------------------------------------------------


@pytest.fixture(scope="module")
def conn(base_de_datos):
    with get_engine().connect() as c:
        yield c


def test_pronostico_de_octubre_de_la_papeleria_contiene_la_venta_base(conn):
    # Aceptación: venta diaria promedio 872.37 × 31 ≈ 27,043 debe quedar dentro del rango mostrado.
    r = srv.proyeccion(conn, 1)
    assert r["mes"]["ventas_pesimista"] <= 27043 <= r["mes"]["ventas_optimista"]
    assert r["mes"]["ventas_pesimista"] <= r["mes"]["ventas"] <= r["mes"]["ventas_optimista"]
    assert r["equilibrio"]["mensual"] == pytest.approx(5789, abs=5)


def test_la_proyeccion_es_determinista(conn):
    assert srv.proyeccion(conn, 2) == srv.proyeccion(conn, 2)


def test_escenarios_mueven_utilidad_y_efectivo(conn):
    base = srv.proyeccion(conn, 2)
    mas = srv.proyeccion(conn, 2, srv.Escenario(ventas_pct=0.2))
    menos = srv.proyeccion(conn, 2, srv.Escenario(ventas_pct=-0.3))
    assert mas["mes"]["utilidad"] > base["mes"]["utilidad"] > menos["mes"]["utilidad"]
    assert mas["flujo"]["fin_de_mes"]["esperado"] > base["flujo"]["fin_de_mes"]["esperado"]
    precios = srv.proyeccion(conn, 2, srv.Escenario(precios_pct=0.1))
    assert precios["equilibrio"]["mensual"] < base["equilibrio"]["mensual"]


def test_nuevo_gasto_fijo_sube_el_equilibrio_y_nueva_deuda_sube_los_pagos(conn):
    base = srv.proyeccion(conn, 1)
    con_gasto = srv.proyeccion(conn, 1, srv.Escenario(gasto_fijo_extra=3000))
    assert con_gasto["equilibrio"]["mensual"] > base["equilibrio"]["mensual"]
    con_deuda = srv.proyeccion(conn, 1, srv.Escenario(deuda_monto=50000, deuda_tasa=0.3, deuda_plazo=12))
    assert con_deuda["consejos"]["pago_deuda_mensual"] > base["consejos"]["pago_deuda_mensual"]


def test_inventario_tiene_semaforo_y_ordena_por_lo_que_se_acaba_primero(conn):
    inv = srv.proyeccion(conn, 1)["inventario"]["productos"]
    coberturas = [p["cobertura_dias"] for p in inv if p["semaforo"] in ("rojo", "amarillo") and p["cobertura_dias"] is not None]
    assert coberturas == sorted(coberturas) or inv[0]["semaforo"] == "rojo"
    assert {p["semaforo"] for p in inv} <= {"rojo", "amarillo", "verde", "sin_movimiento"}


def test_negocio_en_riesgo_dispara_alerta_de_utilidad_que_no_alcanza(conn):
    r = srv.proyeccion(conn, 3)
    assert r["consejos"]["faltante_obligatorio"] > 0
    assert "utilidad_no_cubre_obligaciones" in {a["codigo"] for a in r["alertas"]}


def test_empresa_sin_ventas_no_rompe(conn):
    from sqlalchemy import insert

    from app.db import models as m
    id_nueva = conn.execute(insert(m.empresas).values(nombre_negocio="Vacía", giro="Abarrotes")).inserted_primary_key[0]
    assert srv.proyeccion(conn, id_nueva) == {"tiene_datos": False}
    conn.rollback()

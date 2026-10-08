"""Impuestos: ISR por régimen, IVA, clasificador de deducciones y cálculo mensual con la base de demostración."""

import pytest

from app.db.session import get_engine
from app.impuestos import formulas as f
from app.impuestos import servicio as srv
from app.impuestos.clasificador import clasificar, tasa_iva_gasto
from app.impuestos.parametros import parametros, tasa_iva_sugerida

P = parametros(2026)
TABLA_RESICO = P["resico"]["tabla_mensual"]
TARIFA = P["tarifa_art_96_mensual"]


# --- Parámetros en configuración ---------------------------------------------------------------


def test_parametros_con_anio_de_vigencia():
    assert P["anio"] == 2026
    assert parametros(2030)["anio"] == 2026          # sin año nuevo, usa el vigente más reciente
    assert P["iva"]["tasa_general"] == 0.16


def test_iva_sugerido_por_categoria():
    assert tasa_iva_sugerida("Básicos", "Frijol negro", 2026) == 0.0
    assert tasa_iva_sugerida("Frutas y verduras", "Jitomate", 2026) == 0.0
    assert tasa_iva_sugerida("Bebidas", "Coca-Cola 2 L", 2026) == 0.16
    assert tasa_iva_sugerida("Bebidas", "Agua Ciel 1 L", 2026) == 0.0
    assert tasa_iva_sugerida("Cuadernos", "Cuaderno profesional", 2026) == 0.16
    assert tasa_iva_sugerida("Botanas y dulces", "Sabritas", 2026) == 0.16


# --- IVA ---------------------------------------------------------------------------------------


def test_iva_incluido_en_el_precio():
    assert f.base_sin_iva(116, 0.16) == pytest.approx(100)
    assert f.iva_incluido(116, 0.16) == pytest.approx(16)
    assert f.iva_incluido(100, 0.0) == 0


def test_iva_a_pagar_y_saldo_a_favor():
    assert f.iva_a_pagar(1000, 400)["a_pagar"] == 600
    r = f.iva_a_pagar(200, 500)
    assert r["a_pagar"] == 0 and r["saldo_a_favor"] == 300
    assert f.iva_a_pagar(1000, 400, saldo_favor_previo=700)["saldo_a_favor"] == 100


# --- ISR ---------------------------------------------------------------------------------------


def test_resico_caso_de_aceptacion():
    r = f.isr_resico(26750, TABLA_RESICO)
    assert r["tasa"] == 0.011
    assert round(r["isr_a_pagar"]) == 294


@pytest.mark.parametrize("ingreso,tasa", [(10000, 0.01), (25000, 0.01), (25000.01, 0.011), (60000, 0.015), (100000, 0.02), (250000, 0.025)])
def test_resico_tramos(ingreso, tasa):
    assert f.tasa_resico(ingreso, TABLA_RESICO) == tasa


def test_resico_con_retencion_de_personas_morales():
    r = f.isr_resico(20000, TABLA_RESICO, retenciones=20000 * 0.0125)
    assert r["isr_a_pagar"] == pytest.approx(200 - 250 if False else 0)       # la retención supera el ISR: no hay pago


def test_tarifa_art_96_mensual():
    assert f.isr_tarifa(0, TARIFA) == 0
    assert f.isr_tarifa(1000, TARIFA) == pytest.approx((1000 - 746.05) * 0.064 + 14.32)
    assert f.isr_tarifa(20000, TARIFA) == pytest.approx((20000 - 15487.72) * 0.2136 + 1640.18)


def test_tarifa_acumulada_multiplica_limites_por_los_meses():
    assert f.isr_tarifa(60000, TARIFA, 3) == pytest.approx(f.isr_tarifa(20000, TARIFA, 1) * 3)


def test_pago_provisional_612_descuenta_pagos_previos():
    r = f.pago_provisional_612(100000, 40000, 0, 0, TARIFA, 3, pagos_previos=1000)
    base = 60000
    assert r["base"] == base
    assert r["pago_provisional"] == pytest.approx(f.isr_tarifa(base, TARIFA, 3) - 1000)


def test_pago_provisional_601_usa_coeficiente_de_utilidad():
    r = f.pago_provisional_601(1_000_000, 0.2, 0.30, pagos_previos=20000)
    assert r["isr_acumulado"] == 60000 and r["pago_provisional"] == 40000


def test_ptu_y_limite_resico():
    assert f.ptu(500000, 0.10) == 50000 and f.ptu(-5, 0.10) == 0
    assert f.limite_resico_alcanzado(1_000_000, 3_500_000, 0.85) == "ok"
    assert f.limite_resico_alcanzado(3_000_000, 3_500_000, 0.85) == "cerca"
    assert f.limite_resico_alcanzado(3_600_000, 3_500_000, 0.85) == "excedido"


def test_depreciacion_autos_con_tope():
    dep = P["depreciacion"]
    assert f.depreciacion(300000, "autos", dep).monto_deducible_anual == 43750.0     # 175,000 × 25 %
    assert f.depreciacion(10000, "mobiliario_equipo", dep).monto_deducible_anual == 1000.0
    assert f.depreciacion(20000, "equipo_computo", dep).monto_deducible_anual == 6000.0


def test_codigo_de_regimen():
    assert f.codigo_regimen("RESICO") == "626"
    assert f.codigo_regimen("Persona Física con Actividad Empresarial") == "612"
    assert f.codigo_regimen("General de Ley", "moral") == "601"
    assert f.codigo_regimen(None) == "626"


# --- Clasificador de deducciones ----------------------------------------------------------------


def cl(concepto, categoria="Servicios", monto=500.0, cfdi=True, medio="transferencia", uso="negocio", regimen="612"):
    return clasificar(concepto, categoria, monto, cfdi, medio, uso, regimen, P["iva"]["limite_pago_efectivo"], P["deducciones"])


def test_gasto_normal_es_deducible():
    c = cl("Renta del local", "Renta", 5000)
    assert c.estado == "deducible" and c.monto_deducible == 5000 and c.acredita_iva


def test_sin_cfdi_no_es_deducible_y_es_corregible():
    c = cl("Reparaciones menores", "Mantenimiento", cfdi=False)
    assert c.estado == "no_deducible" and c.perdido_por == "sin_cfdi" and not c.acredita_iva


def test_efectivo_mayor_a_2000_no_es_deducible_pero_menor_si():
    assert cl("Mantenimiento de refrigeradores", "Mantenimiento", 2500, medio="efectivo").estado == "no_deducible"
    assert cl("Mantenimiento de refrigeradores", "Mantenimiento", 1500, medio="efectivo").estado == "deducible"


def test_gasolina_solo_si_se_paga_con_medio_bancarizado():
    assert cl("Gasolina para surtir", "Fletes", 200, medio="efectivo").estado == "no_deducible"
    assert cl("Gasolina para surtir", "Fletes", 200, medio="tarjeta").estado == "deducible"


def test_restaurantes_solo_8_5_por_ciento():
    c = cl("Comida con proveedores", "Otros", 1000)
    assert c.estado == "parcial" and c.monto_deducible == 85.0


def test_renta_de_autos_tope_diario():
    c = cl("Renta de auto para entregas", "Fletes", 900)
    assert c.estado == "parcial" and c.monto_deducible == 200.0


def test_personales_multas_y_regalos_no_se_deducen():
    assert cl("Despensa de la casa", uso="personal").estado == "no_deducible"
    assert cl("Multa de tránsito", "Otros").estado == "no_deducible"
    assert cl("Regalo para cliente", "Otros").estado == "no_deducible"


def test_resico_no_deduce_para_isr_pero_si_acredita_iva():
    c = cl("Renta del local", "Renta", 5000, regimen="626")
    assert c.estado == "no_deducible" and c.acredita_iva and c.perdido_por is None
    sin_factura = cl("Renta del local", "Renta", 5000, cfdi=False, regimen="626")
    assert not sin_factura.acredita_iva


def test_sueldos_no_llevan_iva():
    assert tasa_iva_gasto("Sueldo de ayudante", "Sueldos") == 0.0
    assert tasa_iva_gasto("Internet", "Servicios") == 0.16


# --- Cálculo mensual con la base de demostración --------------------------------------------------


@pytest.fixture(scope="module")
def conn(base_de_datos):
    with get_engine().connect() as c:
        yield c


def test_papeleria_resico_isr_con_tasa_del_mes(conn):
    r = srv.calcular(conn, 1)
    ultimo = r["meses"][-1]
    assert r["configuracion"]["regimen"] == "626"
    assert ultimo["isr"] == pytest.approx(ultimo["ingresos"] * f.tasa_resico(ultimo["ingresos"], TABLA_RESICO), abs=0.01)
    assert r["total_a_pagar"] == pytest.approx(r["isr"] + r["iva_a_pagar"], abs=0.02)
    assert r["fecha_limite"] == "2026-10-17"
    assert "RESICO" in r["mensaje_resico"]


def test_abarrotes_vende_a_tasa_cero_y_tiene_saldo_a_favor_de_iva(conn):
    r = srv.calcular(conn, 2)
    assert r["explicacion_iva"]
    assert r["iva_a_pagar"] < 0.02 * r["meses"][-1]["ventas"]                 # casi no paga IVA
    assert any(x["saldo_a_favor"] > 0 for x in r["meses"])                    # y algunos meses le queda saldo a favor


def test_boutique_actividades_empresariales_deduce_compras(conn):
    r = srv.calcular(conn, 3)
    assert r["configuracion"]["regimen"] == "612"
    assert sum(x["deducciones"] for x in r["meses"]) > 0
    resico = r["comparador_regimen"]["resico_anual"]
    assert resico > r["comparador_regimen"]["actividades_empresariales_anual"]      # la compra fuerte de temporada baja el ISR en 612


def test_dinero_perdido_por_gastos_sin_factura(conn):
    r = srv.calcular(conn, 2)
    perdido = r["perdido_por_no_deducir"]
    assert perdido["gastos"] > 0 and perdido["monto"] > 0 and perdido["iva"] > 0


def test_calendario_y_aviso_legal(conn):
    r = srv.calcular(conn, 1)
    assert r["calendario"][0]["fecha"] == "2026-10-17" and r["calendario"][0]["estimado"] is False
    assert "No sustituye la declaración" in r["aviso_legal"]


def test_gastos_clasificados_traen_el_motivo(conn):
    filas = srv.gastos_clasificados(conn, 2)
    assert filas and all(g["motivo"] and g["estado"] in ("deducible", "parcial", "no_deducible") for g in filas)


def test_el_calculo_es_determinista(conn):
    assert srv.calcular(conn, 3) == srv.calcular(conn, 3)

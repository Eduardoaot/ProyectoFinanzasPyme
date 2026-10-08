"""Fórmulas de deudas, incluidos los casos de aceptación del prompt."""

import pytest

from app.deudas import formulas as f


def test_pago_fijo_credito_60mil_28_por_ciento_24_meses():
    assert round(f.pago_fijo(60000, 0.28, 24)) == 3293


def test_pago_minimo_tarjeta_caso_de_aceptacion():
    # máx(1.5 % × 8,450 + 380.25 + 60.84 ; 1.25 % × 20,000) = 567.84
    assert f.pago_minimo_tarjeta(8450, 20000, 0.54, True) == 567.84


def test_pago_minimo_usa_el_limite_cuando_es_mayor():
    assert f.pago_minimo_tarjeta(1000, 40000, 0.0, True) == 500.0


def test_pago_minimo_nunca_supera_lo_que_se_debe():
    assert f.pago_minimo_tarjeta(100, 40000, 0.0, True) == 100.0


def test_tabla_amortizacion_termina_en_cero_y_suma_el_capital():
    tabla = f.tabla_amortizacion(60000, 0.28, 24, aplica_iva=True)
    assert len(tabla) == 24
    assert tabla[-1].saldo == 0
    assert tabla[0].interes == 1400.0 and tabla[0].iva == 224.0
    assert sum(fila.capital for fila in tabla) == pytest.approx(60000, abs=0.5)


def test_meses_para_liquidar_coincide_con_la_tabla():
    cuota = f.pago_fijo(60000, 0.28, 24)
    assert f.meses_para_liquidar(60000, 0.28, cuota) == pytest.approx(24, abs=0.01)


def test_alerta_la_deuda_nunca_baja():
    # El interés con IVA del mes es 10,000 × 0.54/12 × 1.16 = 522
    assert f.nunca_baja(10000, 0.54, 500, aplica_iva=True)
    assert f.meses_para_liquidar(10000, 0.54, 500, aplica_iva=True) is None
    assert not f.nunca_baja(10000, 0.54, 800, aplica_iva=True)


def test_deuda_sin_interes_se_paga_en_saldo_entre_pago():
    assert f.meses_para_liquidar(9000, 0.0, 1500) == pytest.approx(6)


def test_tasa_promedio_ponderada():
    assert f.tasa_promedio_ponderada([(100, 0.5), (300, 0.1)]) == pytest.approx(0.2)
    assert f.tasa_promedio_ponderada([]) is None


def test_dscr_y_semaforos():
    assert f.dscr(5000, 4000) == 1.25
    assert f.semaforo_dscr(1.25) == "verde" and f.semaforo_dscr(1.1) == "amarillo" and f.semaforo_dscr(0.9) == "rojo"
    assert f.semaforo_peso_deuda(0.10) == "verde" and f.semaforo_peso_deuda(0.2) == "amarillo"
    assert f.semaforo_peso_deuda(0.31) == "rojo"


def test_capacidad_de_endeudamiento():
    r = f.capacidad_endeudamiento(10000, 3000, 0.0, 12)
    assert r["pago_maximo"] == 5000.0 and r["monto_equivalente"] == 60000.0
    assert f.capacidad_endeudamiento(1000, 5000, 0.3)["pago_maximo"] == 0.0


def _deudas():
    return [
        f.DeudaSim(1, "Banco", "credito_simple", 10000, 0.36, aplica_iva=False, pago=1000),
        f.DeudaSim(2, "Familiar", "prestamo_personal", 2000, 0.0, pago=500),
    ]


def test_avalancha_paga_menos_interes_que_el_plan_actual():
    actual = f.simular(_deudas(), "actual")
    avalancha = f.simular(_deudas(), "avalancha", extra_mensual=500)
    assert avalancha.interes_total < actual.interes_total
    assert avalancha.meses_totales < actual.meses_totales


def test_avalancha_vs_bola_de_nieve_ordenes_distintos():
    av = f.simular(_deudas(), "avalancha", extra_mensual=500)
    bn = f.simular(_deudas(), "bola_de_nieve", extra_mensual=500)
    assert av.meses[0].pagos[1] == 1500 and av.meses[0].pagos[2] == 500    # el extra va a la tasa más alta
    assert bn.meses[0].pagos[2] == 1000 and bn.meses[0].pagos[1] == 1000   # el extra va al saldo más chico
    assert av.interes_total <= bn.interes_total


def test_simulacion_es_determinista():
    a = f.simular(_deudas(), "avalancha", extra_mensual=300)
    b = f.simular(_deudas(), "avalancha", extra_mensual=300)
    assert a == b


def test_simulacion_detecta_deuda_que_nunca_termina():
    d = [f.DeudaSim(1, "Banco", "credito_simple", 10000, 0.60, pago=400)]
    assert f.simular(d, "actual", max_meses=60).meses_totales is None


def test_ahorro_por_pago_extra():
    d = f.DeudaSim(1, "Banco", "credito_simple", 20000, 0.30, pago=1200)
    r = f.ahorro_pago_extra(d, 300)
    assert r["ahorro_interes"] > 0 and r["meses_ahorrados"] > 0
    assert r["interes_con_extra"] < r["interes_sin_extra"]

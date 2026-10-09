"""Tendencia de margen y ventas por producto (funciones puras)."""

import pytest

from app.forecasting.tendencias import (EntradaProducto, MesProducto, confianza, proyectar_unidades, regresion_lineal,
                                        tendencia_producto)


def mes(unidades: float, precio: float, costo: float) -> MesProducto:
    return MesProducto(unidades, unidades * precio, unidades * costo)


def producto(meses, precio_lista=10.0, stock=30.0, compras=None) -> EntradaProducto:
    return EntradaProducto(1, "Libreta", "pieza", precio_lista, stock, meses, compras)


def test_regresion_lineal_recta_perfecta():
    pendiente, intercepto, r2 = regresion_lineal([2, 4, 6, 8])
    assert pendiente == pytest.approx(2)
    assert intercepto == pytest.approx(2)
    assert r2 == pytest.approx(1)


def test_regresion_lineal_sin_tendencia():
    pendiente, _, r2 = regresion_lineal([5, 5, 5, 5])
    assert pendiente == 0 and r2 == 0


def test_confianza():
    assert confianza(0.9, 6) == "alta"
    assert confianza(0.4, 6) == "media"
    assert confianza(0.1, 6) == "baja"
    assert confianza(0.99, 3) == "baja"          # con 3 meses nunca es confiable


def test_precio_de_lista_mayor_mejora_el_margen():
    # Vendía a $10 con costo $6 (margen 40 %); su precio de lista ya es $12 → (12 − 6) / 12 = 50 %.
    t = tendencia_producto(producto([mes(30, 10, 6)] * 6, precio_lista=12), 2)
    assert t.margen_ultimo == pytest.approx(0.40)
    assert t.margen_proyectado == pytest.approx(0.50)
    assert t.clasificacion == "mejora"
    assert t.efecto_precio == pytest.approx(0.10) and t.efecto_costo == pytest.approx(0)


def test_compras_mas_caras_entran_completas_si_el_inventario_es_poco():
    # 30 piezas al mes ≈ 1 al día; 30 de stock ≈ 30 días < 2 meses → todo el costo nuevo ($7) ya entra.
    t = tendencia_producto(producto([mes(30, 10, 6)] * 6, compras=7.0), 2)
    assert t.fraccion_costo_nuevo == 1.0
    assert t.margen_proyectado == pytest.approx(0.30)
    assert t.clasificacion == "empeora"


def test_compras_mas_caras_entran_parcial_si_hay_mucho_inventario():
    # 120 días de inventario y horizonte de 1 mes → solo ~25 % del costo nuevo entra.
    t = tendencia_producto(producto([mes(30, 10, 6)] * 6, stock=120 * 30 / 30.4, compras=10.0), 1)
    assert t.fraccion_costo_nuevo == pytest.approx(0.25, abs=0.01)
    assert t.margen_proyectado == pytest.approx((10 - (6 + 0.25 * 4)) / 10, abs=0.005)


def test_sin_cambios_es_estable():
    t = tendencia_producto(producto([mes(30, 10, 6)] * 6, compras=6.0), 2)
    assert t.clasificacion == "estable"
    assert t.cambio_pts == pytest.approx(0)


def test_menos_de_dos_meses_con_ventas_no_se_estima():
    assert tendencia_producto(producto([MesProducto(0, 0, 0)] * 5 + [mes(10, 10, 6)]), 2) is None


def test_sin_un_anio_de_historia_usa_la_recta_con_limite():
    u = proyectar_unidades([10, 20, 30, 40, 50, 60], 2)
    assert u.metodo == "tendencia"
    assert u.confianza == "media"                # la recta nunca es "alta": no ve temporadas
    # La recta daría 80, pero el límite es +50 % sobre el promedio de los últimos 3 meses (50) → 75.
    assert u.unidades == pytest.approx(75)


def test_con_un_anio_de_historia_respeta_la_temporada():
    # Oct-24 … Dic-25 (15 meses). Pico en septiembre; este año se vende 10 % más que el anterior.
    anio_pasado = [40, 50, 90, 30, 30, 30, 30, 30, 30, 60, 100, 200]        # oct-24 … sep-25
    este_anio = [44, 55, 99]                                              # oct-25 … dic-25
    serie = anio_pasado + este_anio
    u = proyectar_unidades(serie, 9)                                      # septiembre de 2026
    assert u.metodo == "mismo_mes_anio_pasado"
    assert u.crecimiento_anual == pytest.approx(0.10)
    assert u.unidades == pytest.approx(200 * 1.10)
    assert u.confianza == "alta"
    # Al mes siguiente del pico la recta subiría; este método baja con la temporada.
    despues_del_pico = proyectar_unidades(anio_pasado + [66, 110, 220], 1)
    assert despues_del_pico.unidades < 220


def test_cambio_de_unidades_contra_el_ultimo_mes():
    t = tendencia_producto(producto([mes(u, 10, 6) for u in (10, 20, 30, 40, 50, 60)]), 2)
    assert t.cambio_unidades == pytest.approx(75 / 60 - 1)

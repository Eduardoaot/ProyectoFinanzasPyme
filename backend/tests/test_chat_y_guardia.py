"""Detección de intención/periodo y guardia de cifras."""

from datetime import date

import pytest

from app.chat.intenciones import detectar_periodo, intencion_por_reglas
from app.llm.guardia import cifras_permitidas, filtrar

CORTE = date(2026, 9, 30)


@pytest.mark.parametrize("pregunta, intencion", [
    ("¿Estoy ganando?", "ganancia"),
    ("¿Qué producto me deja más?", "productos_top"),
    ("¿Qué productos me dejan menos?", "productos_bajo"),
    ("¿Dónde gasto demasiado?", "gastos"),
    ("¿Me va a alcanzar el efectivo?", "flujo"),
    ("Hazme un análisis completo", "analisis_completo"),
    ("¿Es rentable mi negocio?", "ganancia"),
    ("¿Debería pedir un préstamo?", "financiamiento"),
    ("¿Qué se me va a agotar?", "inventario"),
    ("¿Cuál es mi punto de equilibrio?", "equilibrio"),
    ("¿Cómo subo mi Excel?", "importar"),
    ("¿Cuánto pago de IVA?", "impuestos"),
    ("y en julio?", None),
    ("Explícame en Saldo proyectado qué significa bola de nieve y abalancha", "concepto"),
    ("¿Qué es el punto de equilibrio?", "concepto"),
    ("¿Qué es el CAT?", "concepto"),
    ("¿Me conviene avalancha o bola de nieve?", "deudas"),
    ("¿Cuánto debo en mis tarjetas?", "deudas"),
    ("Dime cuáles son los productos que crees que van a mejorar su % en 2 meses", "tendencia_productos"),
    ("¿Qué productos se van a vender más?", "tendencia_productos"),
    ("¿Qué es lo que más gasto?", "gastos"),          # "qué es" sin término del glosario no es concepto
])
def test_intencion(pregunta, intencion):
    assert intencion_por_reglas(pregunta) == intencion


def test_glosario_prefiere_el_termino_mas_largo():
    from app.chat.glosario import buscar

    assert [c.clave for c in buscar("que es el margen de seguridad")] == ["margen_seguridad"]
    assert [c.clave for c in buscar("saldo proyectado bola de nieve y abalancha")] == ["saldo_proyectado", "bola_de_nieve", "avalancha"]
    assert buscar("en que categoria esta") == []          # "cat" solo como palabra completa


@pytest.mark.parametrize("pregunta, meses", [
    ("¿qué productos van a mejorar en 2 meses?", 2), ("en tres meses", 3), ("el próximo mes", 1),
    ("este trimestre", 3), ("¿qué productos van a mejorar?", 2), ("en 18 meses", 12),
    ("¿qué se va a vender más en diciembre?", 3), ("¿y en febrero?", 5), ("en septiembre", 12),
])
def test_horizonte_de_la_pregunta(pregunta, meses):
    from app.chat.hechos_avanzados import horizonte_meses

    assert horizonte_meses(pregunta, date(2026, 9, 1)) == meses


@pytest.mark.parametrize("pregunta, desde, hasta", [
    ("¿cuánto gané en agosto?", date(2026, 8, 1), date(2026, 8, 31)),
    ("ventas de diciembre", date(2025, 12, 1), date(2025, 12, 31)),
    ("agosto 2025", date(2025, 8, 1), date(2025, 8, 31)),
    ("el mes pasado", date(2026, 8, 1), date(2026, 8, 31)),
    ("en lo que va del año", date(2026, 1, 1), CORTE),
    ("el año pasado", date(2025, 1, 1), date(2025, 12, 31)),
    ("últimos 3 meses", date(2026, 7, 1), CORTE),
])
def test_periodo(pregunta, desde, hasta):
    p = detectar_periodo(pregunta, CORTE, None)
    assert (p.desde, p.hasta, p.explicito) == (desde, hasta, True)


def test_periodo_por_defecto():
    p = detectar_periodo("¿Estoy ganando?", CORTE, (date(2026, 3, 1), date(2026, 3, 31)))
    assert (p.desde, p.explicito) == (date(2026, 3, 1), False)


def test_guardia_conserva_cifras_permitidas():
    permitidas = cifras_permitidas(["Ventas: $170,000", "Margen: 38.2%"])
    texto, rechazadas = filtrar("Vendiste $170,000 con margen de 38.2%. Sigue así.", permitidas)
    assert texto == "Vendiste $170,000 con margen de 38.2%. Sigue así." and rechazadas == []


def test_guardia_quita_oracion_con_cifra_inventada():
    permitidas = cifras_permitidas(["Ventas: $170,000"])
    texto, rechazadas = filtrar("Vendiste $170,000. Tu margen es 41%. Cuida tus gastos.", permitidas)
    assert "41" not in texto and "Cuida tus gastos." in texto and rechazadas == ["41"]


def test_guardia_normaliza_formatos():
    permitidas = cifras_permitidas(["$1,200.00"])
    assert filtrar("Pagaste $1,200 de renta.", permitidas)[1] == []

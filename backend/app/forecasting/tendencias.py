"""Hacia dónde van el margen y las ventas de cada producto (funciones puras, sin LLM).

Margen a `h` meses. El margen de un producto no sigue una línea recta: cambia a saltos cuando
cambias el precio o cuando el proveedor cambia el costo. Por eso se proyecta con dos señales que
ya se conocen hoy:
  1. Precio: el precio de lista actual frente al precio promedio que cobraste el último mes.
  2. Costo: el costo de tus compras recientes frente al costo de lo que vendiste el último mes.
     El costo nuevo entra poco a poco, porque primero vendes lo que ya tenías:
     fracción = min(1, días del horizonte / días de inventario).
  costo_h  = costo_último + fracción × (costo_compras − costo_último)
  margen_h = (precio_lista − costo_h) / precio_lista

Ventas en unidades del mes `h`. Las tiendas tienen temporadas (regreso a clases, fiestas patrias,
diciembre), así que una recta sobre los últimos meses engaña: después del pico de septiembre
"vería" un crecimiento que no va a pasar. Por eso, si hay un año de historia:
  unidades_h = unidades del mismo mes del año pasado × crecimiento anual,
  crecimiento anual = últimos 3 meses ÷ los mismos 3 meses del año pasado (entre 0.5 y 2).
Sin un año de historia se usa la recta de los últimos 6 meses, con confianza a lo más "media".
"""

import statistics
from dataclasses import dataclass
from typing import Literal

UMBRAL_CAMBIO_MARGEN = 0.01        # 1 punto porcentual
DIAS_POR_MES = 30.4
LIMITE_CAMBIO_UNIDADES = 0.5       # la recta no puede mover las ventas más de ±50 %
LIMITES_CRECIMIENTO_ANUAL = (0.5, 2.0)
DISPERSION_MAXIMA = 1.5            # crecimiento parejo: el mes que más creció no supera 1.5× al que menos
MESES_ANIO = 12
MESES_RECTA = 6

Clasificacion = Literal["mejora", "empeora", "estable"]
Confianza = Literal["alta", "media", "baja"]
MetodoUnidades = Literal["mismo_mes_anio_pasado", "tendencia"]


@dataclass(frozen=True)
class MesProducto:
    unidades: float
    ingreso: float
    costo: float


@dataclass(frozen=True)
class EntradaProducto:
    id_producto: int
    nombre: str
    unidad: str
    precio_lista: float
    stock: float
    meses: list[MesProducto]                 # meses completos (hasta 15), el más antiguo primero; puede haber ceros
    costo_compras_recientes: float | None


@dataclass(frozen=True)
class ProyeccionUnidades:
    unidades: float
    confianza: Confianza
    metodo: MetodoUnidades
    mismo_mes_anio_pasado: float | None
    crecimiento_anual: float | None


@dataclass(frozen=True)
class TendenciaProducto:
    id_producto: int
    nombre: str
    unidad: str
    margen_ultimo: float
    margen_proyectado: float
    cambio_pts: float
    efecto_precio: float
    efecto_costo: float
    precio_ultimo: float
    precio_lista: float
    costo_ultimo: float
    costo_compras: float | None
    fraccion_costo_nuevo: float
    clasificacion: Clasificacion
    unidades_ultimo: float
    unidades: ProyeccionUnidades
    cambio_unidades: float | None            # frente al último mes


def regresion_lineal(y: list[float]) -> tuple[float, float, float]:
    """Recta por mínimos cuadrados contra x = 0..n−1. Devuelve (pendiente, intercepto, R²)."""
    n = len(y)
    if n < 2:
        return 0.0, (y[0] if y else 0.0), 0.0
    x_med, y_med = (n - 1) / 2, statistics.fmean(y)
    sxx = sum((i - x_med) ** 2 for i in range(n))
    sxy = sum((i - x_med) * (v - y_med) for i, v in enumerate(y))
    pendiente = sxy / sxx
    intercepto = y_med - pendiente * x_med
    sst = sum((v - y_med) ** 2 for v in y)
    sse = sum((v - (intercepto + pendiente * i)) ** 2 for i, v in enumerate(y))
    r2 = 1 - sse / sst if sst > 0 else 0.0
    return pendiente, intercepto, max(0.0, r2)


def confianza(r2: float, n: int) -> Confianza:
    if n < 4:
        return "baja"
    return "alta" if r2 >= 0.6 else "media" if r2 >= 0.3 else "baja"


def _margen(precio: float, costo: float) -> float:
    return (precio - costo) / precio if precio > 0 else 0.0


def proyectar_unidades(unidades: list[float], horizonte_meses: int) -> ProyeccionUnidades:
    """Unidades del mes que está `horizonte_meses` después del último de la serie."""
    n = len(unidades)
    objetivo = n - 1 + horizonte_meses - MESES_ANIO       # el mismo mes, un año antes
    if n >= MESES_ANIO + 3 and objetivo >= 0:
        recientes, hace_un_anio = unidades[-3:], unidades[-MESES_ANIO - 3:-MESES_ANIO]
        if sum(hace_un_anio) > 0 and unidades[objetivo] > 0:
            minimo, maximo = LIMITES_CRECIMIENTO_ANUAL
            crecimiento = min(maximo, max(minimo, sum(recientes) / sum(hace_un_anio)))
            razones = [r / a for r, a in zip(recientes, hace_un_anio) if r > 0 and a > 0]
            parejo = len(razones) == 3 and max(razones) / min(razones) <= DISPERSION_MAXIMA
            return ProyeccionUnidades(unidades[objetivo] * crecimiento, "alta" if parejo else "media",
                                      "mismo_mes_anio_pasado", unidades[objetivo], crecimiento - 1)
    serie = unidades[-MESES_RECTA:]
    pendiente, intercepto, r2 = regresion_lineal(serie)
    promedio = statistics.fmean(serie[-3:])
    estimado = intercepto + pendiente * (len(serie) - 1 + horizonte_meses)
    if promedio > 0:
        estimado = min(promedio * (1 + LIMITE_CAMBIO_UNIDADES), max(promedio * (1 - LIMITE_CAMBIO_UNIDADES), estimado))
    nivel: Confianza = "media" if confianza(r2, len(serie)) == "alta" else "baja"
    return ProyeccionUnidades(max(0.0, estimado), nivel, "tendencia", None, None)


def tendencia_producto(p: EntradaProducto, horizonte_meses: int) -> TendenciaProducto | None:
    """None si el producto vendió en menos de 2 meses de la ventana."""
    con_ventas = [m for m in p.meses if m.unidades > 0 and m.ingreso > 0]
    if len(con_ventas) < 2:
        return None
    ultimo = con_ventas[-1]
    precio_ultimo = ultimo.ingreso / ultimo.unidades
    costo_ultimo = ultimo.costo / ultimo.unidades
    precio_lista = p.precio_lista if p.precio_lista > 0 else precio_ultimo

    venta_diaria = ultimo.unidades / DIAS_POR_MES
    dias_inventario = p.stock / venta_diaria if venta_diaria > 0 else None
    dias_horizonte = horizonte_meses * DIAS_POR_MES
    fraccion = 1.0 if not dias_inventario else min(1.0, dias_horizonte / dias_inventario)
    costo_h = costo_ultimo if p.costo_compras_recientes is None else (
        costo_ultimo + fraccion * (p.costo_compras_recientes - costo_ultimo))

    margen_ultimo = _margen(ultimo.ingreso, ultimo.costo)
    con_precio_nuevo = _margen(precio_lista, costo_ultimo)
    proyectado = _margen(precio_lista, costo_h)
    cambio = proyectado - margen_ultimo
    clasificacion: Clasificacion = ("mejora" if cambio >= UMBRAL_CAMBIO_MARGEN
                                    else "empeora" if cambio <= -UMBRAL_CAMBIO_MARGEN else "estable")

    unidades = proyectar_unidades([m.unidades for m in p.meses], horizonte_meses)
    unidades_ultimo = p.meses[-1].unidades

    return TendenciaProducto(
        id_producto=p.id_producto, nombre=p.nombre, unidad=p.unidad, margen_ultimo=margen_ultimo,
        margen_proyectado=proyectado, cambio_pts=cambio,
        efecto_precio=con_precio_nuevo - margen_ultimo, efecto_costo=proyectado - con_precio_nuevo,
        precio_ultimo=precio_ultimo, precio_lista=precio_lista, costo_ultimo=costo_ultimo,
        costo_compras=p.costo_compras_recientes, fraccion_costo_nuevo=fraccion, clasificacion=clasificacion,
        unidades_ultimo=unidades_ultimo, unidades=unidades,
        cambio_unidades=unidades.unidades / unidades_ultimo - 1 if unidades_ultimo > 0 else None,
    )


def tendencias(productos: list[EntradaProducto], horizonte_meses: int) -> list[TendenciaProducto]:
    """Todos los productos con datos suficientes, ordenados del que más mejora al que más empeora."""
    resultado = [t for p in productos if (t := tendencia_producto(p, horizonte_meses)) is not None]
    return sorted(resultado, key=lambda t: (-t.cambio_pts, t.nombre))

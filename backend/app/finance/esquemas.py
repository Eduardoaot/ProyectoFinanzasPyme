"""Modelos Pydantic de salida del módulo de finanzas (los usa la API y el chatbot)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Periodo(BaseModel):
    desde: date
    hasta: date
    etiqueta: str


class KPIs(BaseModel):
    ventas: float
    costo_ventas: float
    utilidad_bruta: float
    gastos_operacion: float
    gastos_fijos: float
    gastos_variables: float
    impuestos: float = 0.0
    impuestos_calculados: bool = False      # fase 2
    utilidad: float
    margen: float | None
    margen_bruto: float | None
    unidades: float


class Variaciones(BaseModel):
    ventas: float | None
    costo_ventas: float | None
    utilidad_bruta: float | None
    gastos_operacion: float | None
    utilidad: float | None
    margen_pp: float | None


class PuntoSerie(BaseModel):
    periodo: str
    etiqueta: str
    ventas: float
    costo: float
    gastos: float
    utilidad_bruta: float
    utilidad: float


class DatoClave(BaseModel):
    etiqueta: str
    valor: float | str | None
    formato: Literal["dinero", "porcentaje", "numero", "texto"]
    ayuda: str = ""


class Resumen(BaseModel):
    periodo: Periodo
    periodo_anterior: Periodo
    kpis: KPIs
    kpis_anterior: KPIs
    variaciones: Variaciones
    serie: list[PuntoSerie]
    datos_clave: list[DatoClave]


class LineaEstado(BaseModel):
    clave: str
    etiqueta: str
    termino_tecnico: str
    monto: float
    porcentaje: float | None
    nivel: Literal["ingreso", "resta", "subtotal", "total", "info"]
    nota: str = ""


class CategoriaGasto(BaseModel):
    categoria: str
    tipo: str
    monto: float
    porcentaje: float


class PuntoEquilibrio(BaseModel):
    gastos_fijos_mensuales: float
    margen_contribucion: float | None
    punto_equilibrio_mensual: float | None
    ventas_mensuales_promedio: float
    margen_seguridad_mensual: float | None
    cubierto: bool | None


class Finanzas(BaseModel):
    periodo: Periodo
    estado_resultados: list[LineaEstado]
    mensual: list[PuntoSerie]
    distribucion_gastos: list[CategoriaGasto]
    punto_equilibrio: PuntoEquilibrio


Semaforo = Literal["verde", "amarillo", "rojo", "sin_movimiento"]


class ProductoMetricas(BaseModel):
    id_producto: int
    nombre: str
    categoria: str
    unidad: str
    unidades: float
    ventas: float
    costo: float
    utilidad: float
    margen: float | None
    precio_venta: float
    costo_promedio: float
    margen_actual: float | None
    stock_actual: float
    stock_minimo: float
    venta_diaria: float
    dias_inventario: float | None
    semaforo: Semaforo
    valor_inventario: float


class ResumenInventario(BaseModel):
    verde: int
    amarillo: int
    rojo: int
    sin_movimiento: int
    valor_total: float          # existencias de hoy a costo: el dinero que tienes en mercancía
    valor_a_precio_venta: float  # lo que entraría si vendieras todas las existencias de hoy
    unidades_total: float
    compras_periodo: float      # lo que gastaste en mercancía dentro del periodo elegido


class Productos(BaseModel):
    periodo: Periodo
    productos: list[ProductoMetricas]
    top_utilidad: list[ProductoMetricas]
    bajo_margen: list[ProductoMetricas]
    inventario: ResumenInventario


class PuntoFlujoMensual(BaseModel):
    periodo: str
    etiqueta: str
    entradas: float
    compras: float
    gastos: float
    neto: float
    saldo: float


class PuntoSaldo(BaseModel):
    fecha: date
    saldo: float


class PuntoProyeccion(BaseModel):
    fecha: date
    saldo: float
    inferior: float
    superior: float


class Proyeccion(BaseModel):
    metodo: str
    dias: int
    fecha_corte: date
    saldo_actual: float
    saldo_proyectado: float
    inferior: float
    superior: float
    entradas_diarias: float
    salidas_diarias: float
    puntos: list[PuntoProyeccion]


class Flujo(BaseModel):
    periodo: Periodo
    saldo_inicial: float
    entradas: float
    compras: float
    gastos: float
    saldo_final: float
    mensual: list[PuntoFlujoMensual]
    diario: list[PuntoSaldo]
    proyeccion: Proyeccion | None

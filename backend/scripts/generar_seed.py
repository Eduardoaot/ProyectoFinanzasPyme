"""Genera el dataset sintético de demo: 3 microempresas, octubre 2024 a septiembre 2026.

Uso (desde la carpeta backend/):
    python -m scripts.generar_seed            # escribe database/schema.sql y database/cuentas_claras.sql
    python -m scripts.generar_seed --cargar   # además inserta los datos en DATABASE_URL (.env)

La simulación es de inventario: cada día se venden unidades (Poisson con estacionalidad),
el stock baja y, al llegar al punto de reorden, se registra una compra. Así ventas, compras
y stock_actual son coherentes entre sí. Los datos son reproducibles (semilla fija).

La Papelería cuadra exactamente con el caso base de CLAUDE.md §12 (enero-septiembre 2026):
ventas $170,000 · costo de ventas $75,000 · gastos de operación $30,000.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
from sqlalchemy import insert
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.api.seguridad import hash_password
from app.db import models as m

INICIO = dt.date(2024, 10, 1)
FIN = dt.date(2026, 9, 30)
VENTANA_2026 = (dt.date(2026, 1, 1), dt.date(2026, 9, 30))
CASO_BASE = {"ventas": Decimal("170000.00"), "costo": Decimal("75000.00"), "gastos": Decimal("30000.00")}
PASSWORD_DEMO = "Demo2026!"
SEMILLA = 2026
MIN_REGISTROS = 700
RAIZ = Path(__file__).resolve().parents[2]
CENT = Decimal("0.01")

# Ajustes generales de precios de proveedores y de venta (inflación por escalones).
AJUSTES_COSTO = [(dt.date(2025, 2, 1), 1.03), (dt.date(2025, 8, 1), 1.025), (dt.date(2026, 2, 1), 1.03), (dt.date(2026, 6, 1), 1.02)]
AJUSTES_PRECIO = [(dt.date(2025, 3, 1), 1.04), (dt.date(2025, 9, 1), 1.03), (dt.date(2026, 3, 1), 1.04)]


def d2(valor: float | Decimal) -> Decimal:
    return Decimal(str(valor)).quantize(CENT, ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Definición de las empresas
# ---------------------------------------------------------------------------


@dataclass
class Prod:
    nombre: str
    categoria: str
    precio: float
    costo: float
    demanda: float                      # unidades por día (antes de estacionalidad y calibración)
    unidad: str = "pieza"
    temporada: dict[int, float] = field(default_factory=dict)
    proveedor: str = ""
    salto_costo: tuple[dt.date, float] | None = None   # el proveedor sube el costo y el precio no
    stock_final: int | None = None                     # escenario de stock crítico (por agotarse)
    lote_minimo: int = 1
    margen_fijo: bool = False                          # no se ajusta al cuadrar el caso base


@dataclass
class GastoFijo:
    concepto: str
    categoria: str
    monto: float
    dias: tuple[int, ...] = (1,)        # 31 = último día del mes
    cada_meses: int = 1
    desde: dt.date | None = None
    aumento_anual: float = 0.0


@dataclass
class GastoVar:
    concepto: str
    categoria: str
    por_mes: float
    minimo: float
    maximo: float
    meses: dict[int, float] = field(default_factory=dict)
    desde: dt.date | None = None


@dataclass
class Empresa:
    clave: str
    nombre: str
    giro: str
    ciudad: str
    regimen: str | None
    saldo_inicial: float
    productos: list[Prod]
    estacional: dict[int, float]
    semana: list[float]                 # lunes..domingo
    tendencia_anual: float
    cobertura_dias: float               # cuánto inventario compra en cada resurtido
    dias_reorden: float                 # punto de reorden en días de venta
    gastos_fijos: list[GastoFijo]
    gastos_var: list[GastoVar]
    objetivo_ventas_2026: float
    redondeo_precio: str                # "entero", "medio" o "boutique"
    eventos_gasto: list[tuple[dt.date, str, str, float]] = field(default_factory=list)
    compra_temporada: tuple[list[str], list[dt.date]] | None = None  # productos y fechas de compra fuerte
    hora_apertura: tuple[int, int] = (9, 20)


PAPELERIA = Empresa(
    clave="papeleria",
    nombre="Papelería El Lápiz Feliz",
    giro="Papelería",
    ciudad="Ciudad de México",
    regimen="RESICO",
    saldo_inicial=12000,
    estacional={1: 1.25, 2: 0.95, 3: 0.9, 4: 0.85, 5: 0.9, 6: 0.85, 7: 1.1, 8: 1.9, 9: 1.15, 10: 0.92, 11: 0.88, 12: 0.6},
    semana=[1.1, 1.1, 1.05, 1.05, 1.1, 0.85, 0.35],
    tendencia_anual=0.06,
    cobertura_dias=24,
    dias_reorden=5,
    objetivo_ventas_2026=170000,
    redondeo_precio="entero",
    hora_apertura=(8, 20),
    productos=[
        Prod("Cuaderno profesional raya 100 h", "Cuadernos", 45, 24, 2.0, proveedor="Distribuidora Scribe",
             temporada={8: 1.6, 1: 1.3}, stock_final=3),
        Prod("Cuaderno profesional cuadro 100 h", "Cuadernos", 45, 24, 2.0, proveedor="Distribuidora Scribe", temporada={8: 1.6, 1: 1.3}),
        Prod("Cuaderno forma francesa", "Cuadernos", 28, 14, 1.0, proveedor="Distribuidora Scribe", temporada={8: 1.5}),
        Prod("Lápiz Mirado No. 2", "Escritura", 7, 3, 4.0, proveedor="Papelera del Centro"),
        Prod("Pluma BIC azul", "Escritura", 8, 3.5, 5.0, proveedor="Papelera del Centro"),
        Prod("Pluma BIC negra", "Escritura", 8, 3.5, 4.0, proveedor="Papelera del Centro"),
        Prod("Borrador Pelikan", "Escritura", 6, 2.5, 2.0, proveedor="Papelera del Centro"),
        Prod("Sacapuntas metálico", "Escritura", 10, 4, 1.0, proveedor="Papelera del Centro"),
        Prod("Colores Prismacolor 12", "Arte", 95, 52, 0.5, proveedor="Papelera del Centro", temporada={8: 1.8}),
        Prod("Colores Maped 12", "Arte", 55, 28, 0.5, proveedor="Papelera del Centro", temporada={8: 1.8}),
        Prod("Plumones Crayola 10", "Arte", 65, 34, 0.4, proveedor="Papelera del Centro"),
        Prod("Pegamento en barra Pritt", "Escolares", 32, 17, 1.0, proveedor="Papelera del Centro"),
        Prod("Resistol 850", "Escolares", 25, 12, 1.0, proveedor="Papelera del Centro"),
        Prod("Tijeras escolares", "Escolares", 22, 10, 0.4, proveedor="Papelera del Centro", temporada={8: 2.0}),
        Prod("Regla 30 cm", "Escolares", 12, 5, 0.5, proveedor="Papelera del Centro", temporada={8: 2.0}),
        Prod("Juego de geometría", "Escolares", 38, 18, 0.3, proveedor="Papelera del Centro", temporada={8: 2.0}),
        Prod("Calculadora científica Casio", "Calculadoras", 420, 388, 0.06, proveedor="Electrónica Escolar", margen_fijo=True),
        Prod("Calculadora básica", "Calculadoras", 85, 45, 0.1, proveedor="Electrónica Escolar"),
        Prod("Hojas blancas paquete 100", "Papel", 45, 24, 0.6, proveedor="Papelera del Centro"),
        Prod("Papel bond carta resma", "Papel", 120, 78, 0.25, proveedor="Papelera del Centro"),
        Prod("Cartulina blanca", "Papel", 9, 4, 3.0, proveedor="Papelera del Centro"),
        Prod("Papel china pliego", "Papel", 4, 1.5, 6.0, proveedor="Papelera del Centro", temporada={9: 2.2, 10: 1.6, 11: 1.4}),
        Prod("Papel crepé", "Papel", 9, 4, 1.5, proveedor="Papelera del Centro", temporada={9: 1.8}),
        Prod("Foami tamaño carta", "Manualidades", 6, 2.5, 3.0, proveedor="Papelera del Centro"),
        Prod("Folder tamaño carta", "Oficina", 4, 1.6, 4.0, proveedor="Papelera del Centro"),
        Prod("Sobre manila", "Oficina", 5, 2, 2.0, proveedor="Papelera del Centro"),
        Prod("Corrector líquido", "Escritura", 22, 11, 0.5, proveedor="Papelera del Centro"),
        Prod("Marcatextos amarillo", "Escritura", 18, 8, 0.8, proveedor="Papelera del Centro"),
        Prod("Cinta adhesiva transparente", "Oficina", 15, 6, 1.0, proveedor="Papelera del Centro"),
        Prod("Lapicera escolar", "Escolares", 65, 30, 0.1, proveedor="Papelera del Centro", temporada={8: 3.0}),
        Prod("Mochila escolar básica", "Mochilas", 380, 210, 0.05, proveedor="Mochilas del Bajío", temporada={8: 4.0, 1: 1.5}),
        Prod("Copias blanco y negro", "Servicios", 1, 0.40, 60.0, unidad="hoja", proveedor="Papelera del Centro", lote_minimo=2500),
        Prod("Impresión a color", "Servicios", 5, 1.8, 6.0, unidad="hoja", proveedor="Papelera del Centro", lote_minimo=200),
        Prod("Engrapadora", "Oficina", 75, 40, 0.05, proveedor="Papelera del Centro"),
        Prod("Caja de grapas", "Oficina", 18, 8, 0.2, proveedor="Papelera del Centro"),
    ],
    gastos_fijos=[
        GastoFijo("Renta del local", "Renta", 1200, dias=(1,), aumento_anual=0.05),
        GastoFijo("Internet y teléfono", "Servicios", 389, dias=(10,)),
        GastoFijo("Agua", "Servicios", 90, dias=(15,)),
        GastoFijo("Luz (CFE, bimestral)", "Servicios", 420, dias=(20,), cada_meses=2),
    ],
    gastos_var=[
        GastoVar("Bolsas y empaque", "Insumos", 4, 25, 70),
        GastoVar("Tóner y mantenimiento de copiadora", "Mantenimiento", 1.2, 150, 380),
        GastoVar("Artículos de limpieza", "Insumos", 3, 20, 60),
        GastoVar("Transporte a proveedor", "Fletes", 5, 30, 90, meses={8: 1.8, 7: 1.4}),
        GastoVar("Comisión de terminal bancaria", "Comisiones", 4, 25, 90, meses={8: 1.8}),
        GastoVar("Papelería interna y etiquetas", "Insumos", 2, 15, 45),
        GastoVar("Garrafones de agua", "Insumos", 4, 18, 22),
        GastoVar("Reparaciones menores", "Mantenimiento", 0.6, 80, 350),
        GastoVar("Publicidad (volantes)", "Publicidad", 0.6, 80, 250, meses={7: 3, 8: 2}),
        GastoVar("Recargas de saldo", "Servicios", 3, 20, 50),
    ],
)

ABARROTES = Empresa(
    clave="abarrotes",
    nombre="Abarrotes Doña Lupita",
    giro="Abarrotes",
    ciudad="Guadalajara, Jal.",
    regimen="RESICO",
    saldo_inicial=40000,
    estacional={1: 0.95, 2: 0.95, 3: 1.0, 4: 1.05, 5: 1.05, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.05, 10: 1.0, 11: 1.02, 12: 1.15},
    semana=[0.95, 0.9, 0.92, 0.95, 1.05, 1.2, 1.15],
    tendencia_anual=0.08,
    cobertura_dias=9,
    dias_reorden=2.5,
    objetivo_ventas_2026=900000,
    redondeo_precio="medio",
    hora_apertura=(7, 22),
    productos=[
        Prod("Coca-Cola 2 L", "Bebidas", 42, 39.5, 6, proveedor="Embotelladora local", temporada={4: 1.2, 5: 1.3, 6: 1.2}),
        Prod("Coca-Cola 600 ml", "Bebidas", 20, 16, 10, proveedor="Embotelladora local", temporada={4: 1.2, 5: 1.3, 6: 1.2}),
        Prod("Agua Ciel 1 L", "Bebidas", 14, 9.5, 7, proveedor="Embotelladora local", temporada={4: 1.3, 5: 1.4, 6: 1.2}),
        Prod("Jugo Jumex 1 L", "Bebidas", 30, 23, 2, proveedor="Abastos Jalisco"),
        Prod("Leche Lala 1 L", "Lácteos", 29, 25, 12, proveedor="Lala distribuidor",
             stock_final=4),
        Prod("Leche Alpura 1 L", "Lácteos", 30, 26, 6, proveedor="Alpura distribuidor"),
        Prod("Huevo blanco", "Básicos", 48, 38, 5, unidad="kg", proveedor="Granja San Juan",
             salto_costo=(dt.date(2026, 9, 1), 1.14)),
        Prod("Tortillas", "Básicos", 24, 19, 9, unidad="kg", proveedor="Tortillería La Güera"),
        Prod("Pan Bimbo grande", "Panadería", 58, 47, 3, proveedor="Bimbo ruta"),
        Prod("Bolillo", "Panadería", 3, 2, 40, proveedor="Panadería El Trigal"),
        Prod("Frijol negro", "Básicos", 38, 29, 3, unidad="kg", proveedor="Abastos Jalisco"),
        Prod("Arroz", "Básicos", 32, 24, 3, unidad="kg", proveedor="Abastos Jalisco"),
        Prod("Azúcar", "Básicos", 34, 27, 3, unidad="kg", proveedor="Abastos Jalisco"),
        Prod("Aceite Nutrioli 1 L", "Básicos", 48, 39, 2.5, proveedor="Abastos Jalisco"),
        Prod("Sal 1 kg", "Básicos", 14, 9, 0.8, proveedor="Abastos Jalisco"),
        Prod("Harina de maíz Maseca 1 kg", "Básicos", 25, 19, 2, proveedor="Abastos Jalisco"),
        Prod("Sopa de pasta", "Abarrotes", 18, 12.5, 5, proveedor="Abastos Jalisco"),
        Prod("Atún Dolores", "Abarrotes", 26, 19.5, 3, proveedor="Abastos Jalisco", temporada={3: 1.8, 4: 1.6}),
        Prod("Chiles La Costeña 220 g", "Abarrotes", 22, 16, 2, proveedor="Abastos Jalisco"),
        Prod("Frijoles refritos lata", "Abarrotes", 25, 18.5, 2, proveedor="Abastos Jalisco"),
        Prod("Mayonesa McCormick", "Abarrotes", 45, 35, 1.2, proveedor="Abastos Jalisco"),
        Prod("Café Nescafé 120 g", "Abarrotes", 85, 68, 0.8, proveedor="Abastos Jalisco", temporada={12: 1.3, 1: 1.3}),
        Prod("Galletas Marías", "Botanas y dulces", 22, 16, 3, proveedor="Abastos Jalisco"),
        Prod("Sabritas 45 g", "Botanas y dulces", 20, 15.5, 8, proveedor="Sabritas ruta"),
        Prod("Doritos 60 g", "Botanas y dulces", 22, 17, 5, proveedor="Sabritas ruta"),
        Prod("Gansito Marinela", "Botanas y dulces", 18, 13.5, 4, proveedor="Bimbo ruta"),
        Prod("Chocolate Carlos V", "Botanas y dulces", 12, 8.5, 4, proveedor="Abastos Jalisco"),
        Prod("Jabón Zote", "Limpieza", 25, 18, 1.5, proveedor="Abastos Jalisco"),
        Prod("Detergente Ariel 1 kg", "Limpieza", 52, 41, 1.5, proveedor="Abastos Jalisco"),
        Prod("Suavitel 850 ml", "Limpieza", 35, 26, 1.2, proveedor="Abastos Jalisco"),
        Prod("Cloro Cloralex 1 L", "Limpieza", 22, 15.5, 2, proveedor="Abastos Jalisco"),
        Prod("Papel higiénico 4 rollos", "Higiene", 38, 29, 2.5, proveedor="Abastos Jalisco"),
        Prod("Pasta dental Colgate", "Higiene", 32, 24, 1.2, proveedor="Abastos Jalisco"),
        Prod("Shampoo Sedal", "Higiene", 55, 42, 0.8, proveedor="Abastos Jalisco"),
        Prod("Jabón de tocador Palmolive", "Higiene", 18, 12.5, 2, proveedor="Abastos Jalisco"),
        Prod("Jamón de pavo", "Salchichonería", 140, 108, 1.2, unidad="kg", proveedor="Salchichonería FUD"),
        Prod("Queso Oaxaca", "Salchichonería", 160, 125, 1.0, unidad="kg", proveedor="Cremería Los Altos"),
        Prod("Salchicha", "Salchichonería", 95, 72, 1.2, unidad="kg", proveedor="Salchichonería FUD"),
        Prod("Jitomate", "Frutas y verduras", 28, 20, 4, unidad="kg", proveedor="Mercado de Abastos"),
        Prod("Cebolla", "Frutas y verduras", 26, 18, 2.5, unidad="kg", proveedor="Mercado de Abastos"),
        Prod("Papa", "Frutas y verduras", 30, 22, 2.5, unidad="kg", proveedor="Mercado de Abastos"),
        Prod("Plátano", "Frutas y verduras", 22, 15, 3, unidad="kg", proveedor="Mercado de Abastos"),
        Prod("Limón", "Frutas y verduras", 35, 26, 2, unidad="kg", proveedor="Mercado de Abastos", temporada={4: 1.3, 5: 1.3}),
        Prod("Cerveza Corona 355 ml", "Bebidas", 22, 18, 10, proveedor="Grupo Modelo ruta", temporada={4: 1.3, 5: 1.4, 9: 1.4, 12: 1.4}),
        Prod("Hielo bolsa 5 kg", "Bebidas", 35, 22, 2, proveedor="Hielera Tapatía", temporada={4: 1.8, 5: 2.0, 6: 1.6, 12: 0.5, 1: 0.5}),
    ],
    gastos_fijos=[
        GastoFijo("Renta del local", "Renta", 5000, dias=(1,), aumento_anual=0.05),
        GastoFijo("Sueldo de ayudante (quincena)", "Sueldos", 2000, dias=(15, 31), aumento_anual=0.08),
        GastoFijo("Internet", "Servicios", 399, dias=(5,)),
        GastoFijo("Agua", "Servicios", 220, dias=(12,)),
        GastoFijo("Luz (CFE, bimestral)", "Servicios", 1800, dias=(22,), cada_meses=2),
    ],
    gastos_var=[
        GastoVar("Gas LP", "Servicios", 1, 550, 700),
        GastoVar("Bolsas de plástico", "Insumos", 4, 60, 160),
        GastoVar("Artículos de limpieza", "Insumos", 3, 40, 120),
        GastoVar("Gasolina para surtir", "Fletes", 6, 120, 260),
        GastoVar("Comisión de terminal bancaria", "Comisiones", 4, 80, 220),
        GastoVar("Mantenimiento de refrigeradores", "Mantenimiento", 0.4, 400, 1500),
        GastoVar("Merma de perecederos", "Mermas", 3, 60, 250),
        GastoVar("Recargas y servicios", "Servicios", 2, 50, 120),
        GastoVar("Reparaciones menores", "Mantenimiento", 0.5, 150, 600),
    ],
)

BOUTIQUE = Empresa(
    clave="boutique",
    nombre="Boutique Brisa",
    giro="Ropa y accesorios",
    ciudad="Puebla, Pue.",
    regimen="Persona Física con Actividad Empresarial",
    saldo_inicial=25000,
    estacional={1: 0.8, 2: 1.05, 3: 0.85, 4: 0.9, 5: 1.3, 6: 0.9, 7: 0.85, 8: 0.8, 9: 0.82, 10: 1.0, 11: 1.25, 12: 1.6},
    semana=[0.75, 0.75, 0.8, 0.85, 1.05, 1.6, 1.25],
    tendencia_anual=0.04,
    cobertura_dias=12,
    dias_reorden=3,
    objetivo_ventas_2026=560000,
    redondeo_precio="boutique",
    hora_apertura=(10, 20),
    compra_temporada=(["Chamarra acolchada", "Chamarra de mezclilla", "Suéter tejido", "Botines"],
                      [dt.date(2026, 9, 12), dt.date(2026, 9, 24)]),
    productos=[
        Prod("Blusa básica de algodón", "Blusas", 249, 115, 0.45, proveedor="Textiles Tehuacán"),
        Prod("Blusa de manta bordada", "Blusas", 389, 180, 0.2, proveedor="Artesanías Cuetzalan", temporada={9: 2.0, 5: 1.3}),
        Prod("Playera estampada", "Blusas", 199, 85, 0.4, proveedor="Textiles Tehuacán", temporada={4: 1.3, 5: 1.3, 6: 1.3}),
        Prod("Jeans skinny dama", "Pantalones", 549, 260, 0.3, proveedor="Mezclilleras Tehuacán"),
        Prod("Jeans mom fit", "Pantalones", 599, 285, 0.25, proveedor="Mezclilleras Tehuacán"),
        Prod("Pantalón de vestir", "Pantalones", 499, 235, 0.15, proveedor="Confecciones Atlixco"),
        Prod("Short de mezclilla", "Pantalones", 329, 150, 0.15, proveedor="Mezclilleras Tehuacán", temporada={3: 2.0, 4: 2.5, 5: 2.5, 6: 2.0, 11: 0.3, 12: 0.3, 1: 0.3}),
        Prod("Falda midi plisada", "Faldas y vestidos", 429, 195, 0.12, proveedor="Confecciones Atlixco"),
        Prod("Vestido casual", "Faldas y vestidos", 599, 270, 0.2, proveedor="Confecciones Atlixco", temporada={4: 1.4, 5: 1.6}),
        Prod("Vestido de fiesta", "Faldas y vestidos", 1290, 620, 0.06, proveedor="Confecciones Atlixco", temporada={12: 2.5, 5: 1.5}),
        Prod("Conjunto deportivo", "Deportivo", 699, 330, 0.1, proveedor="Textiles Tehuacán", temporada={1: 2.0}),
        Prod("Leggings deportivos", "Deportivo", 279, 120, 0.2, proveedor="Textiles Tehuacán", temporada={1: 1.8}),
        Prod("Suéter tejido", "Invierno", 549, 250, 0.08, proveedor="Tejidos Chignahuapan", temporada={10: 2.0, 11: 3.0, 12: 3.5, 1: 2.5, 2: 1.2, 5: 0.2, 6: 0.1, 7: 0.1, 8: 0.2}),
        Prod("Chamarra de mezclilla", "Invierno", 899, 430, 0.06, proveedor="Mezclilleras Tehuacán", temporada={10: 2.0, 11: 3.0, 12: 3.0, 1: 2.0, 6: 0.2, 7: 0.2}),
        Prod("Chamarra acolchada", "Invierno", 1190, 560, 0.05, proveedor="Importadora Angelópolis", temporada={11: 3.5, 12: 4.0, 1: 3.0, 2: 1.2, 4: 0.1, 5: 0.1, 6: 0.1, 7: 0.1, 8: 0.1}),
        Prod("Sudadera con capucha", "Invierno", 549, 245, 0.12, proveedor="Textiles Tehuacán", temporada={11: 1.8, 12: 2.0, 1: 1.8}),
        Prod("Pijama dama", "Ropa interior", 349, 160, 0.1, proveedor="Textiles Tehuacán", temporada={12: 2.0}),
        Prod("Bra básico", "Ropa interior", 199, 85, 0.2, proveedor="Textiles Tehuacán"),
        Prod("Calcetas paquete 3", "Ropa interior", 99, 40, 0.3, proveedor="Textiles Tehuacán"),
        Prod("Bolsa de mano", "Accesorios", 459, 210, 0.12, proveedor="Importadora Angelópolis", temporada={5: 2.0, 12: 1.6}),
        Prod("Cinturón de piel", "Accesorios", 249, 105, 0.1, proveedor="Marroquinería León"),
        Prod("Bufanda", "Accesorios", 199, 80, 0.08, proveedor="Tejidos Chignahuapan", temporada={11: 3.0, 12: 3.5, 1: 2.5, 5: 0.1, 6: 0.1, 7: 0.1}),
        Prod("Sandalias", "Calzado", 349, 165, 0.12, proveedor="Calzado León", temporada={3: 2.0, 4: 2.5, 5: 2.5, 6: 1.8, 11: 0.2, 12: 0.3, 1: 0.2}),
        Prod("Tenis blancos", "Calzado", 799, 390, 0.12, proveedor="Calzado León"),
        Prod("Botines", "Calzado", 999, 480, 0.06, proveedor="Calzado León", temporada={10: 2.0, 11: 2.5, 12: 2.5, 1: 2.0, 5: 0.2, 6: 0.2, 7: 0.2}),
        Prod("Lentes de sol", "Accesorios", 179, 60, 0.12, proveedor="Importadora Angelópolis", temporada={3: 2.0, 4: 2.5, 5: 2.0, 12: 0.3}),
        Prod("Aretes de fantasía", "Accesorios", 89, 30, 0.35, proveedor="Importadora Angelópolis", temporada={2: 1.8, 5: 1.8, 12: 1.5}),
        Prod("Gorra", "Accesorios", 199, 85, 0.1, proveedor="Textiles Tehuacán"),
    ],
    gastos_fijos=[
        GastoFijo("Renta del local", "Renta", 7500, dias=(1,), aumento_anual=0.05),
        GastoFijo("Sueldo de vendedora (quincena)", "Sueldos", 3000, dias=(15, 31), aumento_anual=0.08),
        GastoFijo("Sueldo de la dueña (quincena)", "Sueldos", 2000, dias=(15, 31)),
        GastoFijo("Sueldo de segunda vendedora (quincena)", "Sueldos", 3200, dias=(15, 31), desde=dt.date(2026, 9, 1)),
        GastoFijo("Internet y teléfono", "Servicios", 499, dias=(8,)),
        GastoFijo("Luz (CFE, bimestral)", "Servicios", 1400, dias=(18,), cada_meses=2),
        GastoFijo("Sistema de punto de venta", "Software", 299, dias=(3,)),
    ],
    gastos_var=[
        GastoVar("Publicidad en redes sociales", "Publicidad", 3, 150, 450, meses={5: 2, 11: 2, 12: 2}),
        GastoVar("Publicidad en redes sociales (campaña otoño)", "Publicidad", 12, 300, 600, meses={9: 1}, desde=dt.date(2026, 9, 1)),
        GastoVar("Bolsas de regalo y empaque", "Insumos", 3, 80, 220, meses={12: 2, 5: 1.6}),
        GastoVar("Ganchos y etiquetas", "Insumos", 2, 60, 180),
        GastoVar("Comisión de terminal bancaria", "Comisiones", 4, 100, 320, meses={12: 1.6, 5: 1.4}),
        GastoVar("Envíos por paquetería", "Fletes", 3, 90, 220),
        GastoVar("Limpieza del local", "Insumos", 2, 50, 150),
        GastoVar("Transporte a proveedores", "Fletes", 2, 150, 400),
        GastoVar("Arreglos y ajustes de ropa", "Mantenimiento", 2, 60, 200),
        GastoVar("Decoración de aparador", "Publicidad", 0.8, 200, 700, meses={12: 2, 2: 1.5, 9: 1.5}),
    ],
    eventos_gasto=[
        (dt.date(2025, 6, 10), "Mobiliario y exhibidores", "Mantenimiento", 18500),
        (dt.date(2026, 3, 16), "Remodelación del local", "Mantenimiento", 22000),
    ],
)

# Las abarroteras compran a mayoreo con descuento; los dos productos de escenario conservan su margen bajo.
for _p in ABARROTES.productos:
    if _p.nombre not in ("Coca-Cola 2 L", "Huevo blanco"):
        _p.costo = round(_p.costo * 0.96, 2)

EMPRESAS = [PAPELERIA, ABARROTES, BOUTIQUE]

# ---------------------------------------------------------------------------
# Deudas de ejemplo (una situación distinta por negocio) y gastos sin factura
# ---------------------------------------------------------------------------

DEUDAS_DEMO: dict[str, list[dict]] = {
    # Papelería: situación sana (deudas chicas y baratas).
    "papeleria": [
        dict(acreedor="Crédito Simple Santander", tipo="credito_simple", original=25000, saldo=14000, tasa=0.24, plazo=18,
             pago=None, limite=None, inicio=dt.date(2025, 12, 5), corte=None, dia_pago=5, iva=1, comision=0, historial=6),
        dict(acreedor="Proveedor Papelera del Centro", tipo="proveedor", original=4500, saldo=4500, tasa=0.0, plazo=None,
             pago=4500, limite=None, inicio=dt.date(2026, 9, 15), corte=None, dia_pago=15, iva=0, comision=0, historial=0),
    ],
    # Abarrotes: situación apretada.
    "abarrotes": [
        dict(acreedor="Tarjeta BBVA Negocios", tipo="tarjeta_credito", original=0, saldo=8450, tasa=0.54, plazo=None,
             pago=None, limite=20000, inicio=dt.date(2024, 11, 2), corte=12, dia_pago=2, iva=1, comision=0, historial=6),
        dict(acreedor="Crédito Simple Banorte", tipo="credito_simple", original=60000, saldo=41200, tasa=0.28, plazo=24,
             pago=3293, limite=None, inicio=dt.date(2026, 1, 28), corte=None, dia_pago=28, iva=1, comision=0, historial=8),
        dict(acreedor="Proveedor de refrescos", tipo="proveedor", original=6000, saldo=6000, tasa=0.0, plazo=None,
             pago=6000, limite=None, inicio=dt.date(2026, 9, 15), corte=None, dia_pago=30, iva=0, comision=0, historial=0),
        dict(acreedor="Préstamo familiar", tipo="prestamo_personal", original=15000, saldo=9000, tasa=0.0, plazo=None,
             pago=1500, limite=None, inicio=dt.date(2026, 1, 10), corte=None, dia_pago=10, iva=0, comision=0, historial=4),
    ],
    # Boutique: negocio en riesgo (tarjeta casi al tope y un préstamo muy caro; la cobertura queda por debajo de 1).
    "boutique": [
        dict(acreedor="Tarjeta Santander Negocios", tipo="tarjeta_credito", original=0, saldo=26500, tasa=0.58, plazo=None,
             pago=None, limite=30000, inicio=dt.date(2024, 12, 10), corte=8, dia_pago=28, iva=1, comision=0, historial=6),
        dict(acreedor="Préstamo de financiera rápida", tipo="prestamo_personal", original=40000, saldo=33000, tasa=0.78, plazo=12,
             pago=4300, limite=None, inicio=dt.date(2026, 4, 15), corte=None, dia_pago=15, iva=1, comision=150, historial=5),
        dict(acreedor="Proveedor de ropa Tendencia", tipo="proveedor", original=18000, saldo=18000, tasa=0.0, plazo=None,
             pago=9000, limite=None, inicio=dt.date(2026, 9, 5), corte=None, dia_pago=5, iva=0, comision=0, historial=0),
    ],
}

# Gastos pequeños que en la vida real suelen pagarse en efectivo y sin factura (para mostrar el módulo de impuestos).
SIN_FACTURA = ("Recargas", "Garrafones", "Papelería interna", "Reparaciones menores", "Transporte", "Gasolina",
               "Arreglos y ajustes", "Merma", "Limpieza", "Bolsas")
FONDO_EMERGENCIA = {"papeleria": 5000, "abarrotes": 0, "boutique": 0}
CON_TRABAJADORES = {"papeleria": 0, "abarrotes": 1, "boutique": 1}


def pagos_historicos(d: dict, id_deuda: int, id_empresa: int, ids: dict, pago: float) -> list[dict]:
    """Abonos de los últimos meses, reconstruidos hacia atrás desde el saldo actual (capital, interés e IVA coherentes)."""
    filas, saldo = [], float(d["saldo"])
    i = d["tasa"] / 12
    for k in range(d["historial"]):
        mes = (FIN.year * 12 + FIN.month - 1) - k
        anio, mes0 = divmod(mes, 12)
        dia = min(d["dia_pago"], calendar.monthrange(anio, mes0 + 1)[1])
        fecha = dt.date(anio, mes0 + 1, dia)
        if fecha > FIN:
            continue
        i_ef = i * (1.16 if d["iva"] else 1.0)
        previo = (saldo + pago) / (1 + i_ef)
        interes = previo * i
        iva = interes * 0.16 if d["iva"] else 0.0
        ids["pago"] += 1
        filas.append({"id_pago": ids["pago"], "id_empresa": id_empresa, "id_deuda": id_deuda, "fecha": fecha, "monto": d2(pago),
                      "capital": d2(max(0.0, pago - interes - iva)), "interes": d2(interes), "iva": d2(iva)})
        saldo = previo
    return filas


USUARIOS = [
    # (nombre, email, [(clave_empresa, rol)])
    ("Ana Ruiz", "ana.ruiz@example.com", [("papeleria", "dueno")]),
    ("Guadalupe Martínez", "lupita.martinez@example.com", [("abarrotes", "dueno")]),
    ("Sofía Herrera", "sofia.herrera@example.com", [("boutique", "dueno")]),
    ("Carlos Méndez (contador)", "carlos.mendez@example.com",
     [("papeleria", "consulta"), ("abarrotes", "consulta"), ("boutique", "consulta")]),
]


# ---------------------------------------------------------------------------
# Simulación
# ---------------------------------------------------------------------------


def dias(desde: dt.date, hasta: dt.date):
    actual = desde
    while actual <= hasta:
        yield actual
        actual += dt.timedelta(days=1)


def factor_escalones(fecha: dt.date, escalones: list[tuple[dt.date, float]]) -> float:
    factor = 1.0
    for desde, f in escalones:
        if fecha >= desde:
            factor *= f
    return factor


def redondear_precio(valor: float, modo: str, base: float) -> float:
    if base < 10:                       # precios bajos (copias, bolillo) no cambian
        return base
    if modo == "entero":
        return float(round(valor))
    if modo == "medio":
        return round(valor * 2) / 2
    return float(math.ceil(valor / 10) * 10 - 1)   # boutique: 249, 389, 599...


def precio_en(p: Prod, fecha: dt.date, emp: Empresa) -> float:
    return redondear_precio(p.precio * factor_escalones(fecha, AJUSTES_PRECIO), emp.redondeo_precio, p.precio)


def costo_en(p: Prod, fecha: dt.date) -> float:
    costo = p.costo * factor_escalones(fecha, AJUSTES_COSTO)
    if p.salto_costo and fecha >= p.salto_costo[0]:
        costo *= p.salto_costo[1]
    return costo


@dataclass
class Resultado:
    ventas: list[list]          # [indice_producto, datetime, cantidad, precio, costo]
    compras: list[list]         # [indice_producto, fecha, cantidad, costo]
    stock_inicial: list[int]


def simular(emp: Empresa, mult: float, extra_temporada: int = 0) -> Resultado:
    rng = np.random.default_rng(SEMILLA + len(emp.clave))
    n = len(emp.productos)
    stock = [math.ceil(p.demanda * mult * emp.cobertura_dias) + p.lote_minimo for p in emp.productos]
    stock_inicial = list(stock)
    ventas: list[list] = []
    compras: list[list] = []
    temporada = emp.compra_temporada
    for dia in dias(INICIO, FIN):
        anios = (dia - INICIO).days / 365
        base = mult * emp.estacional[dia.month] * emp.semana[dia.weekday()] * (1 + emp.tendencia_anual) ** anios
        ruido_dia = rng.lognormal(0, 0.15)
        for i, p in enumerate(emp.productos):
            esperado = base * p.demanda * p.temporada.get(dia.month, 1.0)
            q = int(rng.poisson(esperado * ruido_dia))
            q = min(q, stock[i])
            hora = dt.datetime.combine(dia, dt.time(int(rng.integers(*emp.hora_apertura)), int(rng.integers(0, 60))))
            if q > 0:
                ventas.append([i, hora, q, precio_en(p, dia, emp), costo_en(p, dia)])
                stock[i] -= q
            # Demanda esperada "normal" (sin ruido) para decidir el resurtido.
            normal = mult * emp.estacional[dia.month] * (1 + emp.tendencia_anual) ** anios * p.demanda * p.temporada.get(dia.month, 1.0)
            if stock[i] <= normal * emp.dias_reorden + p.lote_minimo * 0.2:
                cantidad = max(p.lote_minimo, math.ceil(normal * emp.cobertura_dias), 2)
                compras.append([i, dia, cantidad, costo_en(p, dia)])
                stock[i] += cantidad
        if temporada and extra_temporada and dia in temporada[1]:
            nombres = temporada[0]
            for i, p in enumerate(emp.productos):
                if p.nombre in nombres:
                    cantidad = max(1, round(extra_temporada / len(temporada[1]) / len(nombres) / costo_en(p, dia)))
                    compras.append([i, dia, cantidad, costo_en(p, dia)])
                    stock[i] += cantidad
    return Resultado(ventas, compras, stock_inicial)


def ventas_en(res: Resultado, desde: dt.date, hasta: dt.date) -> float:
    return sum(v[2] * v[3] for v in res.ventas if desde <= v[1].date() <= hasta)


def calibrar(emp: Empresa) -> tuple[float, Resultado]:
    mult = 1.0
    res = simular(emp, mult)
    for _ in range(6):
        actual = ventas_en(res, *VENTANA_2026)
        if abs(actual / emp.objetivo_ventas_2026 - 1) < 0.008:
            break
        mult *= emp.objetivo_ventas_2026 / actual
        res = simular(emp, mult)
    return mult, res


def generar_gastos(emp: Empresa, rng: np.random.Generator) -> list[list]:
    """Devuelve [fecha, concepto, categoria, tipo, monto]."""
    gastos: list[list] = []
    mes_indice = 0
    anio, mes = INICIO.year, INICIO.month
    while dt.date(anio, mes, 1) <= FIN:
        ultimo = calendar.monthrange(anio, mes)[1]
        inicio_mes = dt.date(anio, mes, 1)
        anios = (inicio_mes - INICIO).days / 365
        for g in emp.gastos_fijos:
            if g.desde and inicio_mes < g.desde.replace(day=1):
                continue
            if mes_indice % g.cada_meses:
                continue
            for d in g.dias:
                monto = round(g.monto * (1 + g.aumento_anual) ** math.floor(anios))
                gastos.append([dt.date(anio, mes, min(d, ultimo)), g.concepto, g.categoria, "fijo", float(monto)])
        for g in emp.gastos_var:
            if g.desde and inicio_mes < g.desde.replace(day=1):
                continue
            for _ in range(int(rng.poisson(g.por_mes * g.meses.get(mes, 1.0)))):
                fecha = dt.date(anio, mes, int(rng.integers(1, ultimo + 1)))
                gastos.append([fecha, g.concepto, g.categoria, "variable", round(float(rng.uniform(g.minimo, g.maximo)), 2)])
        mes_indice += 1
        mes = mes % 12 + 1
        anio += mes == 1
    for fecha, concepto, categoria, monto in emp.eventos_gasto:
        gastos.append([fecha, concepto, categoria, "variable", float(monto)])
    gastos.sort(key=lambda g: g[0])
    return gastos


def saldo_hasta(emp: Empresa, res: Resultado, gastos: list[list], hasta: dt.date) -> float:
    entradas = sum(v[2] * float(v[3]) for v in res.ventas if v[1].date() <= hasta)
    salidas = (sum(c[2] * float(c[3]) for c in res.compras if c[1] <= hasta)
               + sum(float(g[4]) for g in gastos if g[0] <= hasta))
    return emp.saldo_inicial + entradas - salidas


# ---------------------------------------------------------------------------
# Ajuste exacto del caso base (solo Papelería)
# ---------------------------------------------------------------------------


def en_ventana(fecha: dt.date) -> bool:
    return VENTANA_2026[0] <= fecha <= VENTANA_2026[1]


def cuadrar_caso_base(emp: Empresa, res: Resultado, gastos: list[list], rng: np.random.Generator) -> None:
    # 1) Ventas: todos los precios son enteros, así que la diferencia es un entero de pesos.
    #    Se ajusta con la cantidad de copias ($1 c/u) vendidas en la ventana.
    i_copias = next(i for i, p in enumerate(emp.productos) if p.nombre == "Copias blanco y negro")
    for v in res.ventas:
        v[3] = d2(v[3])
        v[4] = d2(v[4])
    diferencia = int(CASO_BASE["ventas"] - sum(v[2] * v[3] for v in res.ventas if en_ventana(v[1].date())))
    filas_copias = [v for v in res.ventas if v[0] == i_copias and en_ventana(v[1].date())]
    paso = 1 if diferencia > 0 else -1
    k = 0
    while diferencia:
        fila = filas_copias[k % len(filas_copias)]
        if paso > 0 or fila[2] > 1:
            fila[2] += paso
            diferencia -= paso
        k += 1

    # 2) Costo de ventas: factor uniforme a todos los costos (ventas, compras, catálogo) y
    #    el residuo de centavos en una venta de 1 unidad.
    #    Los productos con margen_fijo conservan su costo (escenario de margen bajo).
    fijos_idx = {i for i, p in enumerate(emp.productos) if p.margen_fijo}
    costo_fijo = sum(v[2] * v[4] for v in res.ventas if en_ventana(v[1].date()) and v[0] in fijos_idx)
    costo_actual = sum(v[2] * v[4] for v in res.ventas if en_ventana(v[1].date()))
    factor = (CASO_BASE["costo"] - costo_fijo) / (costo_actual - costo_fijo)
    for v in res.ventas:
        if v[0] not in fijos_idx:
            v[4] = d2(v[4] * factor)
    for c in res.compras:
        if c[0] not in fijos_idx:
            c[3] = d2(Decimal(str(c[3])) * factor)
    for i, p in enumerate(emp.productos):
        if i not in fijos_idx:
            p.costo = float(Decimal(str(p.costo)) * factor)
    residuo = CASO_BASE["costo"] - sum(v[2] * v[4] for v in res.ventas if en_ventana(v[1].date()))
    unitaria = next(v for v in res.ventas if en_ventana(v[1].date()) and v[2] == 1 and v[4] > abs(residuo))
    unitaria[4] += residuo

    # 3) Gastos de operación: factor a los gastos variables y residuo en uno de ellos.
    fijos = sum(Decimal(str(g[4])) for g in gastos if g[3] == "fijo" and en_ventana(g[0]))
    variables = sum(Decimal(str(g[4])) for g in gastos if g[3] == "variable" and en_ventana(g[0]))
    factor_g = (CASO_BASE["gastos"] - fijos) / variables
    for g in gastos:
        g[4] = d2(Decimal(str(g[4])) * factor_g) if g[3] == "variable" else d2(g[4])
    residuo_g = CASO_BASE["gastos"] - sum(g[4] for g in gastos if en_ventana(g[0]))
    ultimo_var = next(g for g in reversed(gastos) if g[3] == "variable" and en_ventana(g[0]))
    ultimo_var[4] += residuo_g


# ---------------------------------------------------------------------------
# Construcción de filas
# ---------------------------------------------------------------------------


def construir() -> dict[str, list[dict]]:
    filas: dict[str, list[dict]] = {t: [] for t in ("usuarios", "empresas", "usuarios_empresas", "productos_cat",
                                                     "historial_ventas", "compras_producto", "gastos_operativos",
                                                     "deudas", "pagos_deuda")}
    ids = {"producto": 0, "venta": 0, "compra": 0, "gasto": 0, "deuda": 0, "pago": 0}
    id_por_clave: dict[str, int] = {}

    for id_empresa, emp in enumerate(EMPRESAS, start=1):
        id_por_clave[emp.clave] = id_empresa
        rng_gastos = np.random.default_rng(SEMILLA * 7 + id_empresa)
        mult, res = calibrar(emp)
        gastos = generar_gastos(emp, rng_gastos)

        if emp is PAPELERIA:
            cuadrar_caso_base(emp, res, gastos, rng_gastos)

        if emp.compra_temporada:
            # Compra fuerte de temporada de invierno: se dimensiona para que el flujo proyectado
            # a 30 días quede negativo (alerta 🔴) sin que el efectivo actual sea negativo.
            agosto = dt.date(2026, 8, 31)
            saldo_agosto = saldo_hasta(emp, res, gastos, agosto)
            septiembre_normal = saldo_hasta(emp, res, gastos, FIN) - saldo_hasta(emp, res, gastos, agosto)
            neto_objetivo = -(saldo_agosto + 0.4 * saldo_agosto) / 2
            extra = max(0.0, septiembre_normal - neto_objetivo)
            res = simular(emp, mult, extra_temporada=round(extra))
            print(f"[{emp.clave}] efectivo al 31-ago: {saldo_agosto:,.0f}; compra de temporada: {extra:,.0f}")

        gastos = sorted(gastos, key=lambda g: g[0])

        # Stock final coherente: inicial + compras - ventas.
        stock = list(res.stock_inicial)
        for c in res.compras:
            stock[c[0]] += c[2]
        for v in res.ventas:
            stock[v[0]] -= v[2]
        # Escenario "por agotarse": se reduce la última compra del producto. Después de esa compra
        # el stock solo baja, así que nunca queda negativo en ningún momento.
        for i, p in enumerate(emp.productos):
            if p.stock_final is not None and stock[i] > p.stock_final:
                ultima = max((c for c in res.compras if c[0] == i), key=lambda c: c[1])
                recorte = min(stock[i] - p.stock_final, ultima[2] - 1)
                ultima[2] -= recorte
                stock[i] -= recorte
        assert min(stock) >= 0, f"Stock negativo en {emp.nombre}"

        filas["empresas"].append({
            "id_empresa": id_empresa, "nombre_negocio": emp.nombre, "giro": emp.giro, "ciudad": emp.ciudad,
            "regimen_fiscal": emp.regimen, "saldo_inicial": d2(emp.saldo_inicial), "fecha_saldo_inicial": INICIO,
            "umbrales_alerta": None, "fecha_registro": dt.datetime.combine(INICIO, dt.time(9, 0)),
            "tipo_persona": "fisica", "factura_a_morales": 0, "pct_ventas_morales": 0,
            "tiene_trabajadores": CON_TRABAJADORES[emp.clave], "coeficiente_utilidad": 0.2,
            "fondo_emergencia": d2(FONDO_EMERGENCIA[emp.clave]),
        })

        id_producto = {}
        for i, p in enumerate(emp.productos):
            ids["producto"] += 1
            id_producto[i] = ids["producto"]
            ultimo_precio = next((v[3] for v in reversed(res.ventas) if v[0] == i), precio_en(p, FIN, emp))
            normal = mult * p.demanda * p.temporada.get(10, 1.0)
            filas["productos_cat"].append({
                "id_producto": ids["producto"], "id_empresa": id_empresa, "sku_o_nombre": p.nombre,
                "categoria": p.categoria, "unidad": p.unidad, "stock_actual": d2(stock[i]),
                "stock_minimo": d2(max(1, math.ceil(normal * emp.dias_reorden))),
                "costo_promedio": d2(costo_en(p, FIN)), "precio_venta": d2(ultimo_precio), "id_importacion": None,
            })

        for v in sorted(res.ventas, key=lambda v: v[1]):
            ids["venta"] += 1
            filas["historial_ventas"].append({
                "id_venta": ids["venta"], "id_empresa": id_empresa, "id_producto": id_producto[v[0]],
                "fecha_hora": v[1], "cantidad_vendida": d2(v[2]), "precio_unitario": d2(v[3]),
                "costo_unitario": d2(v[4]), "id_importacion": None,
            })
        for c in sorted(res.compras, key=lambda c: c[1]):
            ids["compra"] += 1
            filas["compras_producto"].append({
                "id_compra": ids["compra"], "id_empresa": id_empresa, "id_producto": id_producto[c[0]],
                "fecha": c[1], "cantidad": d2(c[2]), "costo_unitario": d2(c[3]),
                "proveedor": emp.productos[c[0]].proveedor or None, "id_importacion": None,
            })
        for g in gastos:
            ids["gasto"] += 1
            sin_factura = any(clave.lower() in g[1].lower() for clave in SIN_FACTURA)
            filas["gastos_operativos"].append({
                "id_gasto": ids["gasto"], "id_empresa": id_empresa, "fecha": g[0], "concepto": g[1],
                "categoria": g[2], "tipo": g[3], "monto": d2(g[4]), "id_importacion": None,
                "tiene_cfdi": 0 if sin_factura else 1, "medio_pago": "efectivo" if sin_factura else "transferencia",
                "uso": "negocio",
            })

        for d in DEUDAS_DEMO[emp.clave]:
            ids["deuda"] += 1
            filas["deudas"].append({
                "id_deuda": ids["deuda"], "id_empresa": id_empresa, "acreedor": d["acreedor"], "tipo": d["tipo"],
                "monto_original": d2(d["original"]), "saldo_actual": d2(d["saldo"]), "tasa_interes_anual": d["tasa"], "cat": None,
                "aplica_iva_intereses": d["iva"], "plazo_meses": d["plazo"],
                "pago_mensual": None if d["pago"] is None else d2(d["pago"]),
                "limite_credito": None if d["limite"] is None else d2(d["limite"]), "fecha_inicio": d["inicio"],
                "dia_corte": d["corte"], "dia_limite_pago": d["dia_pago"], "comisiones_mensuales": d2(d["comision"]),
                "tasa_moratoria_anual": None, "uso": "negocio", "estado": "activa",
            })
            if d["historial"]:
                pago = d["pago"] or max(300.0, round(float(d["saldo"]) * 0.06))
                if d["tipo"] == "credito_simple" and d["pago"] is None:
                    i = d["tasa"] / 12
                    pago = round(d["original"] * i / (1 - (1 + i) ** -d["plazo"]), 2)
                filas["pagos_deuda"].extend(pagos_historicos(d, ids["deuda"], id_empresa, ids, pago))

    for id_usuario, (nombre, email, accesos) in enumerate(USUARIOS, start=1):
        filas["usuarios"].append({
            "id_usuario": id_usuario, "nombre": nombre, "email": email,
            "password_hash": hash_password(PASSWORD_DEMO, salt=f"{id_usuario:032x}"),
            "fecha_registro": dt.datetime.combine(INICIO, dt.time(9, 0)),
        })
        for clave, rol in accesos:
            filas["usuarios_empresas"].append({"id_usuario": id_usuario, "id_empresa": id_por_clave[clave], "rol": rol})
    return filas


# ---------------------------------------------------------------------------
# Salida SQL (MySQL) y carga directa
# ---------------------------------------------------------------------------


def sql_valor(valor) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return str(int(valor))
    if isinstance(valor, (int, float, Decimal)):
        return str(valor)
    if isinstance(valor, dt.datetime):
        return f"'{valor:%Y-%m-%d %H:%M:%S}'"
    if isinstance(valor, dt.date):
        return f"'{valor:%Y-%m-%d}'"
    if isinstance(valor, (dict, list)):
        valor = json.dumps(valor, ensure_ascii=False)
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "''") + "'"


def ddl_mysql() -> str:
    dialecto = mysql.dialect()
    partes = [
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "DROP VIEW IF EXISTS v_ventas_diarias;",
    ]
    for tabla in reversed(m.metadata.sorted_tables):
        partes.append(f"DROP TABLE IF EXISTS {tabla.name};")
    partes.append("SET FOREIGN_KEY_CHECKS = 1;\n")
    for tabla in m.metadata.sorted_tables:
        ddl = str(CreateTable(tabla).compile(dialect=dialecto)).strip()
        partes.append(f"{ddl} ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;\n")
        for indice in sorted(tabla.indexes, key=lambda ix: ix.name or ""):
            partes.append(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
        partes.append("")
    partes.append("-- Vista para modelos de series de tiempo (fase 2)")
    partes.append(m.VISTA_VENTAS_DIARIAS.strip() + ";\n")
    return "\n".join(partes)


ENCABEZADO = """-- =====================================================================
-- Cuentas Claras · Plataforma de inteligencia financiera para tiendas
-- {titulo}
-- Generado por backend/scripts/generar_seed.py (no editar a mano).
-- MySQL 8.0+.  Uso:  mysql -u root -p < database/{archivo}
-- =====================================================================

CREATE DATABASE IF NOT EXISTS cuentas_claras CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cuentas_claras;

"""


def escribir_sql(filas: dict[str, list[dict]]) -> None:
    carpeta = RAIZ / "database"
    carpeta.mkdir(exist_ok=True)
    ddl = ddl_mysql()
    (carpeta / "schema.sql").write_text(
        ENCABEZADO.format(titulo="Esquema (sin datos)", archivo="schema.sql") + ddl, encoding="utf-8")

    with open(carpeta / "cuentas_claras.sql", "w", encoding="utf-8", newline="\n") as f:
        f.write(ENCABEZADO.format(titulo="Esquema + datos de demo (3 empresas, oct-2024 a sep-2026)",
                                  archivo="cuentas_claras.sql"))
        f.write(ddl)
        f.write("\n-- Usuarios demo: contraseña para todos = " + PASSWORD_DEMO + "\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\nSTART TRANSACTION;\n\n")
        for tabla, registros in filas.items():
            if not registros:
                continue
            columnas = list(registros[0].keys())
            f.write(f"-- {tabla}: {len(registros)} registros\n")
            for inicio in range(0, len(registros), 1000):
                lote = registros[inicio:inicio + 1000]
                valores = ",\n".join("(" + ", ".join(sql_valor(r[c]) for c in columnas) + ")" for r in lote)
                f.write(f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES\n{valores};\n")
            f.write("\n")
        f.write("COMMIT;\nSET FOREIGN_KEY_CHECKS = 1;\n")


def cargar(filas: dict[str, list[dict]]) -> None:
    from app.db.session import crear_esquema, get_engine

    engine = get_engine()
    m.metadata.drop_all(engine)
    crear_esquema(engine)
    with engine.begin() as conn:
        for tabla, registros in filas.items():
            for inicio in range(0, len(registros), 2000):
                conn.execute(insert(m.metadata.tables[tabla]), registros[inicio:inicio + 2000])
    print(f"Datos cargados en {engine.url.render_as_string(hide_password=True)}")


def resumen(filas: dict[str, list[dict]]) -> None:
    for e in filas["empresas"]:
        ide = e["id_empresa"]
        ventas = [v for v in filas["historial_ventas"] if v["id_empresa"] == ide]
        compras = [c for c in filas["compras_producto"] if c["id_empresa"] == ide]
        movimientos = [g for g in filas["gastos_operativos"] if g["id_empresa"] == ide]
        productos = [p for p in filas["productos_cat"] if p["id_empresa"] == ide]
        v26 = [v for v in ventas if en_ventana(v["fecha_hora"].date())]
        ing = sum(v["cantidad_vendida"] * v["precio_unitario"] for v in v26)
        cos = sum(v["cantidad_vendida"] * v["costo_unitario"] for v in v26)
        gas = sum(g["monto"] for g in movimientos if en_ventana(g["fecha"]))
        ent = sum(v["cantidad_vendida"] * v["precio_unitario"] for v in ventas)
        sal = sum(c["cantidad"] * c["costo_unitario"] for c in compras) + sum(g["monto"] for g in movimientos)
        print(f"\n{e['nombre_negocio']}: productos={len(productos)} ventas={len(ventas)} "
              f"compras={len(compras)} gastos={len(movimientos)}")
        print(f"  Ene-Sep 2026 -> ventas {ing:,.2f} costo {cos:,.2f} gastos {gas:,.2f} "
              f"utilidad {ing - cos - gas:,.2f} margen {(ing - cos - gas) / ing:.1%}")
        print(f"  Efectivo final: {e['saldo_inicial'] + ent - sal:,.2f}")
        for nombre, registros in (("ventas", ventas), ("compras", compras), ("gastos", movimientos)):
            assert len(registros) >= MIN_REGISTROS, f"{e['nombre_negocio']}: solo {len(registros)} {nombre}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cargar", action="store_true", help="insertar también en DATABASE_URL")
    args = parser.parse_args()
    filas = construir()
    resumen(filas)
    escribir_sql(filas)
    print(f"\nSQL escrito en {RAIZ / 'database'}")
    if args.cargar:
        cargar(filas)


if __name__ == "__main__":
    main()

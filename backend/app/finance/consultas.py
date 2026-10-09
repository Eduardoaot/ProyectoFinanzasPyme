"""Consultas SQL de lectura. Todas filtran por id_empresa (CLAUDE.md §8).

Las fechas se envían como texto ISO ('2026-01-01'): MySQL y SQLite (pruebas) las comparan
igual. Las sumas se convierten a Decimal con centavos para no arrastrar errores de float.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Connection, text

CENT = Decimal("0.01")


def dec(valor) -> Decimal:
    if valor is None:
        return Decimal("0.00")
    return Decimal(str(valor)).quantize(CENT, ROUND_HALF_UP)


def a_fecha(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _rango(desde: date, hasta: date) -> dict:
    return {"desde": desde.isoformat(), "hasta_excl": (hasta + timedelta(days=1)).isoformat()}


def empresa(conn: Connection, id_empresa: int) -> dict | None:
    fila = conn.execute(
        text("SELECT id_empresa, nombre_negocio, giro, ciudad, regimen_fiscal, saldo_inicial, "
             "fecha_saldo_inicial, umbrales_alerta FROM empresas WHERE id_empresa = :e"),
        {"e": id_empresa},
    ).mappings().first()
    return dict(fila) if fila else None


def rango_datos(conn: Connection, id_empresa: int) -> tuple[date | None, date | None]:
    fila = conn.execute(
        text("SELECT MIN(fecha_hora) AS minimo, MAX(fecha_hora) AS maximo FROM historial_ventas WHERE id_empresa = :e"),
        {"e": id_empresa},
    ).first()
    if not fila or fila[0] is None:
        return None, None
    return a_fecha(fila[0]), a_fecha(fila[1])


def ventas_diarias(conn: Connection, id_empresa: int, desde: date, hasta: date) -> list[dict]:
    filas = conn.execute(
        text("""
            SELECT DATE(fecha_hora) AS fecha,
                   SUM(cantidad_vendida * precio_unitario) AS ingreso,
                   SUM(cantidad_vendida * costo_unitario)  AS costo,
                   SUM(cantidad_vendida)                   AS unidades
            FROM historial_ventas
            WHERE id_empresa = :e AND fecha_hora >= :desde AND fecha_hora < :hasta_excl
            GROUP BY DATE(fecha_hora)
            ORDER BY fecha
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return [{"fecha": a_fecha(f["fecha"]), "ingreso": dec(f["ingreso"]), "costo": dec(f["costo"]),
             "unidades": dec(f["unidades"])} for f in filas]


def gastos_diarios(conn: Connection, id_empresa: int, desde: date, hasta: date) -> list[dict]:
    """Gastos agrupados por día, categoría y tipo."""
    filas = conn.execute(
        text("""
            SELECT fecha, categoria, tipo, SUM(monto) AS monto
            FROM gastos_operativos
            WHERE id_empresa = :e AND fecha >= :desde AND fecha < :hasta_excl
            GROUP BY fecha, categoria, tipo
            ORDER BY fecha
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return [{"fecha": a_fecha(f["fecha"]), "categoria": f["categoria"], "tipo": f["tipo"], "monto": dec(f["monto"])}
            for f in filas]


def compras_diarias(conn: Connection, id_empresa: int, desde: date, hasta: date) -> list[dict]:
    filas = conn.execute(
        text("""
            SELECT fecha, SUM(cantidad * costo_unitario) AS monto
            FROM compras_producto
            WHERE id_empresa = :e AND fecha >= :desde AND fecha < :hasta_excl
            GROUP BY fecha
            ORDER BY fecha
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return [{"fecha": a_fecha(f["fecha"]), "monto": dec(f["monto"])} for f in filas]


def ventas_por_producto(conn: Connection, id_empresa: int, desde: date, hasta: date) -> dict[int, dict]:
    filas = conn.execute(
        text("""
            SELECT id_producto,
                   SUM(cantidad_vendida)                   AS unidades,
                   SUM(cantidad_vendida * precio_unitario) AS ingreso,
                   SUM(cantidad_vendida * costo_unitario)  AS costo
            FROM historial_ventas
            WHERE id_empresa = :e AND fecha_hora >= :desde AND fecha_hora < :hasta_excl
            GROUP BY id_producto
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return {f["id_producto"]: {"unidades": dec(f["unidades"]), "ingreso": dec(f["ingreso"]), "costo": dec(f["costo"])}
            for f in filas}


def productos(conn: Connection, id_empresa: int) -> list[dict]:
    filas = conn.execute(
        text("""
            SELECT id_producto, sku_o_nombre, categoria, unidad, stock_actual, stock_minimo,
                   costo_promedio, precio_venta
            FROM productos_cat
            WHERE id_empresa = :e
            ORDER BY sku_o_nombre
        """),
        {"e": id_empresa},
    ).mappings()
    return [{**f, "stock_actual": dec(f["stock_actual"]), "stock_minimo": dec(f["stock_minimo"]),
             "costo_promedio": dec(f["costo_promedio"]), "precio_venta": dec(f["precio_venta"])} for f in filas]


def movimientos_acumulados(conn: Connection, id_empresa: int, antes_de: date) -> dict[str, Decimal]:
    """Totales de efectivo desde el inicio hasta el día anterior a `antes_de`."""
    params = {"e": id_empresa, "f": antes_de.isoformat()}
    entradas = conn.execute(
        text("SELECT SUM(cantidad_vendida * precio_unitario) FROM historial_ventas WHERE id_empresa = :e AND fecha_hora < :f"),
        params).scalar()
    compras = conn.execute(
        text("SELECT SUM(cantidad * costo_unitario) FROM compras_producto WHERE id_empresa = :e AND fecha < :f"),
        params).scalar()
    gastos = conn.execute(
        text("SELECT SUM(monto) FROM gastos_operativos WHERE id_empresa = :e AND fecha < :f"), params).scalar()
    return {"entradas": dec(entradas), "compras": dec(compras), "gastos": dec(gastos)}


def precios_por_producto(conn: Connection, id_empresa: int, desde: date, hasta: date) -> dict[int, dict]:
    """Precio y costo unitario promedio ponderado por producto en el periodo."""
    filas = conn.execute(
        text("""
            SELECT id_producto,
                   SUM(cantidad_vendida * precio_unitario) / SUM(cantidad_vendida) AS precio,
                   SUM(cantidad_vendida * costo_unitario)  / SUM(cantidad_vendida) AS costo
            FROM historial_ventas
            WHERE id_empresa = :e AND fecha_hora >= :desde AND fecha_hora < :hasta_excl
            GROUP BY id_producto
            HAVING SUM(cantidad_vendida) > 0
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return {f["id_producto"]: {"precio": dec(f["precio"]), "costo": dec(f["costo"])} for f in filas}


def ventas_productos_diarias(conn: Connection, id_empresa: int, desde: date, hasta: date) -> list[dict]:
    """Unidades, ingreso y costo por producto y día (vista v_ventas_diarias)."""
    filas = conn.execute(
        text("""
            SELECT id_producto, fecha, unidades, ingreso, costo FROM v_ventas_diarias
            WHERE id_empresa = :e AND fecha >= :desde AND fecha < :hasta_excl
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return [{"id_producto": f["id_producto"], "fecha": a_fecha(f["fecha"]), "unidades": dec(f["unidades"]),
             "ingreso": dec(f["ingreso"]), "costo": dec(f["costo"])} for f in filas]


def costo_compras_por_producto(conn: Connection, id_empresa: int, desde: date, hasta: date) -> dict[int, Decimal]:
    """Costo unitario promedio ponderado de las compras de cada producto en el periodo."""
    filas = conn.execute(
        text("""
            SELECT id_producto, SUM(cantidad * costo_unitario) / SUM(cantidad) AS costo
            FROM compras_producto
            WHERE id_empresa = :e AND fecha >= :desde AND fecha < :hasta_excl
            GROUP BY id_producto
            HAVING SUM(cantidad) > 0
        """),
        {"e": id_empresa, **_rango(desde, hasta)},
    ).mappings()
    return {f["id_producto"]: dec(f["costo"]) for f in filas}


def serie_producto(conn: Connection, id_empresa: int, id_producto: int, desde: date, hasta: date) -> list[dict]:
    """Ventas diarias de un producto desde la vista v_ventas_diarias (lista para series de tiempo)."""
    filas = conn.execute(
        text("""
            SELECT fecha, unidades, ingreso FROM v_ventas_diarias
            WHERE id_empresa = :e AND id_producto = :p AND fecha >= :desde AND fecha < :hasta_excl
            ORDER BY fecha
        """),
        {"e": id_empresa, "p": id_producto, **_rango(desde, hasta)},
    ).mappings()
    return [{"fecha": a_fecha(f["fecha"]), "unidades": dec(f["unidades"]), "ingreso": dec(f["ingreso"])} for f in filas]

"""Esquema de la base de datos (fuente única).

A partir de estas tablas se generan:
- `database/schema.sql` y `database/cuentas_claras.sql` (scripts/generar_seed.py),
- la migración inicial de Alembic,
- la base SQLite en memoria de las pruebas.

Toda tabla de negocio lleva `id_empresa` (CLAUDE.md §2.4 y §8).
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    func,
)

metadata = MetaData()

Monto = Numeric(12, 2)      # MXN
Cantidad = Numeric(12, 2)   # piezas o kilos

usuarios = Table(
    "usuarios",
    metadata,
    Column("id_usuario", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(120), nullable=False),
    Column("email", String(160), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("fecha_registro", DateTime, nullable=False, server_default=func.now()),
    comment="Personas que inician sesión en la plataforma",
)

empresas = Table(
    "empresas",
    metadata,
    Column("id_empresa", Integer, primary_key=True, autoincrement=True),
    Column("nombre_negocio", String(150), nullable=False),
    Column("giro", String(80), nullable=False),
    Column("ciudad", String(80), nullable=True),
    Column("regimen_fiscal", String(60), nullable=True, comment="Fase 2: RESICO, PFAE, etc."),
    Column("saldo_inicial", Monto, nullable=False, server_default="0", comment="Efectivo al iniciar el registro"),
    Column("fecha_saldo_inicial", Date, nullable=True),
    Column("umbrales_alerta", JSON, nullable=True, comment="Sobrescribe los umbrales por defecto"),
    Column("tipo_persona", Enum("fisica", "moral", name="tipo_persona"), nullable=False, server_default="fisica"),
    Column("factura_a_morales", Boolean, nullable=False, server_default="0", comment="¿Factura a personas morales? (retención RESICO)"),
    Column("pct_ventas_morales", Numeric(5, 4), nullable=False, server_default="0", comment="Fracción de ventas facturadas a personas morales"),
    Column("tiene_trabajadores", Boolean, nullable=False, server_default="0", comment="Para PTU e IMSS"),
    Column("coeficiente_utilidad", Numeric(6, 4), nullable=False, server_default="0.2", comment="Persona moral: coeficiente del ejercicio anterior"),
    Column("minimo_seguridad", Monto, nullable=True, comment="Efectivo mínimo deseable; null = 15 días de gastos fijos"),
    Column("fondo_emergencia", Monto, nullable=False, server_default="0", comment="Ahorro de emergencia con que ya cuenta"),
    Column("fecha_registro", DateTime, nullable=False, server_default=func.now()),
    comment="Negocios (tiendas) registrados",
)

usuarios_empresas = Table(
    "usuarios_empresas",
    metadata,
    Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), primary_key=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), primary_key=True),
    Column("rol", Enum("dueno", "consulta", name="rol_usuario"), nullable=False, server_default="dueno"),
    comment="Qué usuario puede ver qué empresa",
)

importaciones = Table(
    "importaciones",
    metadata,
    Column("id_importacion", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("id_usuario", Integer, ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True),
    Column("nombre_archivo", String(255), nullable=False),
    Column("tipo_datos", Enum("ventas", "productos", "compras", "gastos", name="tipo_datos"), nullable=False),
    Column("fecha", DateTime, nullable=False, server_default=func.now()),
    Column("estado", Enum("completada", "con_errores", "deshecha", name="estado_importacion"), nullable=False),
    Column("filas_ok", Integer, nullable=False, server_default="0"),
    Column("filas_con_error", Integer, nullable=False, server_default="0"),
    Column("detalle_errores", JSON, nullable=True),
    Index("ix_importaciones_empresa_fecha", "id_empresa", "fecha"),
    comment="Historial de cargas de Excel/CSV (trazabilidad y deshacer)",
)

productos_cat = Table(
    "productos_cat",
    metadata,
    Column("id_producto", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("sku_o_nombre", String(150), nullable=False),
    Column("categoria", String(80), nullable=False, server_default="General"),
    Column("unidad", String(20), nullable=False, server_default="pieza"),
    Column("stock_actual", Cantidad, nullable=False, server_default="0"),
    Column("stock_minimo", Cantidad, nullable=False, server_default="0"),
    Column("costo_promedio", Monto, nullable=False, server_default="0"),
    Column("precio_venta", Monto, nullable=False, server_default="0"),
    Column("tasa_iva", Numeric(4, 2), nullable=True, comment="0.00 o 0.16; null = sugerida según la categoría"),
    Column("lead_time_dias", Integer, nullable=True, comment="Días de entrega del proveedor; null = 3"),
    Column("empaque", Cantidad, nullable=True, comment="Piezas por caja/paquete del proveedor; null = 1"),
    Column("id_importacion", Integer, ForeignKey("importaciones.id_importacion", ondelete="SET NULL"), nullable=True),
    UniqueConstraint("id_empresa", "sku_o_nombre", name="uq_producto_empresa_nombre"),
    Index("ix_productos_empresa_producto", "id_empresa", "id_producto"),
    comment="Registro de productos",
)

historial_ventas = Table(
    "historial_ventas",
    metadata,
    Column("id_venta", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("id_producto", Integer, ForeignKey("productos_cat.id_producto", ondelete="CASCADE"), nullable=False),
    Column("fecha_hora", DateTime, nullable=False),
    Column("cantidad_vendida", Cantidad, nullable=False),
    Column("precio_unitario", Monto, nullable=False),
    Column("costo_unitario", Monto, nullable=False),
    Column("id_importacion", Integer, ForeignKey("importaciones.id_importacion", ondelete="SET NULL"), nullable=True),
    Index("ix_ventas_empresa_fecha", "id_empresa", "fecha_hora"),
    comment="Registro de ventas",
)

compras_producto = Table(
    "compras_producto",
    metadata,
    Column("id_compra", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("id_producto", Integer, ForeignKey("productos_cat.id_producto", ondelete="CASCADE"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("cantidad", Cantidad, nullable=False),
    Column("costo_unitario", Monto, nullable=False),
    Column("proveedor", String(120), nullable=True),
    Column("id_importacion", Integer, ForeignKey("importaciones.id_importacion", ondelete="SET NULL"), nullable=True),
    Index("ix_compras_empresa_fecha", "id_empresa", "fecha"),
    comment="Registro de compras de producto (resurtido de inventario)",
)

gastos_operativos = Table(
    "gastos_operativos",
    metadata,
    Column("id_gasto", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("concepto", String(150), nullable=False),
    Column("categoria", String(80), nullable=False),
    Column(
        "tipo",
        Enum("fijo", "variable", name="tipo_gasto"),
        nullable=False,
        comment="fijo = renta, nómina, servicios; variable = insumos, fletes, comisiones",
    ),
    Column("monto", Monto, nullable=False),
    Column("tiene_cfdi", Boolean, nullable=False, server_default="1", comment="¿Se tiene la factura (CFDI) a nombre de la empresa?"),
    Column("medio_pago", Enum("efectivo", "transferencia", "tarjeta", "cheque", name="medio_pago"), nullable=False,
           server_default="transferencia"),
    Column("uso", Enum("negocio", "personal", name="uso_gasto"), nullable=False, server_default="negocio"),
    Column("id_importacion", Integer, ForeignKey("importaciones.id_importacion", ondelete="SET NULL"), nullable=True),
    Index("ix_gastos_empresa_fecha", "id_empresa", "fecha"),
    comment="Registro de gastos operativos (fijos y variables)",
)

deudas = Table(
    "deudas",
    metadata,
    Column("id_deuda", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("acreedor", String(120), nullable=False),
    Column("tipo", Enum("tarjeta_credito", "credito_simple", "credito_revolvente", "proveedor", "prestamo_personal",
                        "arrendamiento", name="tipo_deuda"), nullable=False),
    Column("monto_original", Monto, nullable=False, server_default="0"),
    Column("saldo_actual", Monto, nullable=False),
    Column("tasa_interes_anual", Numeric(7, 4), nullable=False, server_default="0", comment="Fracción: 0.54 = 54 %"),
    Column("cat", Numeric(7, 4), nullable=True, comment="Costo Anual Total (fracción)"),
    Column("aplica_iva_intereses", Boolean, nullable=False, server_default="0"),
    Column("plazo_meses", Integer, nullable=True),
    Column("pago_mensual", Monto, nullable=True),
    Column("limite_credito", Monto, nullable=True),
    Column("fecha_inicio", Date, nullable=False),
    Column("dia_corte", Integer, nullable=True),
    Column("dia_limite_pago", Integer, nullable=True),
    Column("comisiones_mensuales", Monto, nullable=False, server_default="0"),
    Column("tasa_moratoria_anual", Numeric(7, 4), nullable=True),
    Column("uso", Enum("negocio", "personal", name="uso_deuda"), nullable=False, server_default="negocio"),
    Column("estado", Enum("activa", "liquidada", "vencida", name="estado_deuda"), nullable=False, server_default="activa"),
    Index("ix_deudas_empresa_estado", "id_empresa", "estado"),
    comment="Deudas del negocio (tarjetas, créditos, proveedores, préstamos)",
)

pagos_deuda = Table(
    "pagos_deuda",
    metadata,
    Column("id_pago", Integer, primary_key=True, autoincrement=True),
    Column("id_empresa", Integer, ForeignKey("empresas.id_empresa", ondelete="CASCADE"), nullable=False),
    Column("id_deuda", Integer, ForeignKey("deudas.id_deuda", ondelete="CASCADE"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("monto", Monto, nullable=False),
    Column("capital", Monto, nullable=False),
    Column("interes", Monto, nullable=False, server_default="0"),
    Column("iva", Monto, nullable=False, server_default="0"),
    Index("ix_pagos_deuda_empresa_fecha", "id_empresa", "fecha"),
    comment="Abonos realizados a una deuda",
)

# Vista para alimentar modelos de series de tiempo (fase 2). DATE() funciona en MySQL y SQLite.
VISTA_VENTAS_DIARIAS = """
CREATE VIEW v_ventas_diarias AS
SELECT
    id_empresa,
    id_producto,
    DATE(fecha_hora)                         AS fecha,
    SUM(cantidad_vendida)                    AS unidades,
    SUM(cantidad_vendida * precio_unitario)  AS ingreso,
    SUM(cantidad_vendida * costo_unitario)   AS costo
FROM historial_ventas
GROUP BY id_empresa, id_producto, DATE(fecha_hora)
"""

TABLAS_NEGOCIO = (productos_cat, historial_ventas, compras_producto, gastos_operativos, importaciones)

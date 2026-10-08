"""Proyecciones, impuestos y deudas: datos fiscales de la empresa, IVA/entrega por producto, factura por gasto y deudas.

Es idempotente: en una base nueva la migración 0001 ya crea todo desde models.py (create_all), así que aquí
solo se agrega lo que falte (columnas y tablas) en bases creadas antes de este cambio.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

from app.db import models as m

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

COLUMNAS = {
    "empresas": ["tipo_persona", "factura_a_morales", "pct_ventas_morales", "tiene_trabajadores", "coeficiente_utilidad",
                 "minimo_seguridad", "fondo_emergencia"],
    "productos_cat": ["tasa_iva", "lead_time_dias", "empaque"],
    "gastos_operativos": ["tiene_cfdi", "medio_pago", "uso"],
}


def upgrade() -> None:
    bind = op.get_bind()
    existentes = {t: {c["name"] for c in sa.inspect(bind).get_columns(t)} for t in COLUMNAS}
    for tabla, nombres in COLUMNAS.items():
        for nombre in nombres:
            if nombre not in existentes[tabla]:
                op.add_column(tabla, m.metadata.tables[tabla].c[nombre].copy())
    m.metadata.create_all(bind, tables=[m.deudas, m.pagos_deuda], checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    m.metadata.drop_all(bind, tables=[m.pagos_deuda, m.deudas], checkfirst=True)
    for tabla, nombres in COLUMNAS.items():
        for nombre in reversed(nombres):
            op.drop_column(tabla, nombre)

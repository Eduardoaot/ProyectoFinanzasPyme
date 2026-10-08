"""Acceso a datos de deudas. Toda consulta y todo registro llevan id_empresa (CLAUDE.md §8)."""

import calendar
from datetime import date

from sqlalchemy import Connection, delete, insert, select, update

from app.db import models as m
from app.deudas import formulas as f
from app.finance.periodos import sumar_meses

TIPOS_REVOLVENTES = f.TIPOS_REVOLVENTES


def _num(valor) -> float | None:
    return None if valor is None else float(valor)


def listar(conn: Connection, id_empresa: int, incluir_liquidadas: bool = True) -> list[dict]:
    consulta = select(m.deudas).where(m.deudas.c.id_empresa == id_empresa).order_by(m.deudas.c.id_deuda)
    if not incluir_liquidadas:
        consulta = consulta.where(m.deudas.c.estado != "liquidada")
    return [dict(r) for r in conn.execute(consulta).mappings()]


def obtener(conn: Connection, id_empresa: int, id_deuda: int) -> dict | None:
    fila = conn.execute(select(m.deudas).where(m.deudas.c.id_empresa == id_empresa, m.deudas.c.id_deuda == id_deuda)).mappings().first()
    return dict(fila) if fila else None


def crear(conn: Connection, id_empresa: int, datos: dict) -> int:
    return conn.execute(insert(m.deudas).values(id_empresa=id_empresa, **datos)).inserted_primary_key[0]


def actualizar(conn: Connection, id_empresa: int, id_deuda: int, datos: dict) -> bool:
    r = conn.execute(update(m.deudas).where(m.deudas.c.id_empresa == id_empresa, m.deudas.c.id_deuda == id_deuda).values(**datos))
    return r.rowcount > 0


def eliminar(conn: Connection, id_empresa: int, id_deuda: int) -> bool:
    conn.execute(delete(m.pagos_deuda).where(m.pagos_deuda.c.id_empresa == id_empresa, m.pagos_deuda.c.id_deuda == id_deuda))
    r = conn.execute(delete(m.deudas).where(m.deudas.c.id_empresa == id_empresa, m.deudas.c.id_deuda == id_deuda))
    return r.rowcount > 0


def pagos(conn: Connection, id_empresa: int, id_deuda: int | None = None, limite: int = 200) -> list[dict]:
    consulta = select(m.pagos_deuda).where(m.pagos_deuda.c.id_empresa == id_empresa).order_by(m.pagos_deuda.c.fecha.desc()).limit(limite)
    if id_deuda is not None:
        consulta = consulta.where(m.pagos_deuda.c.id_deuda == id_deuda)
    return [dict(r) for r in conn.execute(consulta).mappings()]


def meses_restantes(d: dict, hoy: date) -> int | None:
    if not d["plazo_meses"]:
        return None
    transcurridos = (hoy.year - d["fecha_inicio"].year) * 12 + hoy.month - d["fecha_inicio"].month
    return max(1, d["plazo_meses"] - transcurridos)


def a_sim(d: dict, hoy: date) -> f.DeudaSim:
    return f.DeudaSim(
        id=d["id_deuda"], acreedor=d["acreedor"], tipo=d["tipo"], saldo=float(d["saldo_actual"]),
        tasa_anual=float(d["tasa_interes_anual"]), aplica_iva=bool(d["aplica_iva_intereses"]), pago=_num(d["pago_mensual"]),
        limite=_num(d["limite_credito"]), comision=float(d["comisiones_mensuales"] or 0), meses_restantes=meses_restantes(d, hoy),
    )


def registrar_pago(conn: Connection, id_empresa: int, d: dict, fecha: date, monto: float) -> dict:
    """Aplica un abono: primero IVA e interés del mes, el resto baja el capital. Si el saldo llega a 0, la deuda se liquida."""
    saldo = float(d["saldo_actual"])
    interes = f.interes_mes(saldo, float(d["tasa_interes_anual"]))
    iva = f.iva_interes(interes, bool(d["aplica_iva_intereses"]))
    monto = min(monto, saldo + interes + iva)
    cargos = min(monto, interes + iva)
    interes_pagado = cargos / (1 + (f.IVA if d["aplica_iva_intereses"] else 0))
    iva_pagado = cargos - interes_pagado
    capital = max(0.0, monto - cargos)
    nuevo = max(0.0, saldo - capital)
    conn.execute(insert(m.pagos_deuda).values(
        id_empresa=id_empresa, id_deuda=d["id_deuda"], fecha=fecha, monto=f.r2(monto), capital=f.r2(capital),
        interes=f.r2(interes_pagado), iva=f.r2(iva_pagado)))
    conn.execute(update(m.deudas).where(m.deudas.c.id_empresa == id_empresa, m.deudas.c.id_deuda == d["id_deuda"]).values(
        saldo_actual=f.r2(nuevo), estado="liquidada" if nuevo <= 0.005 else "activa"))
    return {"monto": f.r2(monto), "capital": f.r2(capital), "interes": f.r2(interes_pagado), "iva": f.r2(iva_pagado),
            "saldo_nuevo": f.r2(nuevo)}


def fecha_de_pago(d: dict, corte: date, mes_offset: int) -> date:
    """Día límite de pago de la deuda en el mes `corte + mes_offset` (por defecto el día 1)."""
    base = sumar_meses(corte.replace(day=1), mes_offset)
    dia = d["dia_limite_pago"] or 1
    return base.replace(day=min(dia, calendar.monthrange(base.year, base.month)[1]))


def pagos_programados(conn: Connection, id_empresa: int, corte: date, meses: int = 4) -> list[tuple[date, float, str]]:
    """Pagos futuros (plan actual) por deuda activa: mes 1 = el mes siguiente al corte."""
    activas = [d for d in listar(conn, id_empresa, incluir_liquidadas=False)]
    if not activas:
        return []
    sims = [a_sim(d, corte) for d in activas]
    resultado = f.simular(sims, "actual", max_meses=max(meses, 1))
    por_id = {d["id_deuda"]: d for d in activas}
    salida = []
    for fila in resultado.meses[:meses]:
        for id_deuda, monto in fila.pagos.items():
            d = por_id[id_deuda]
            comision = float(d["comisiones_mensuales"] or 0)
            salida.append((fecha_de_pago(d, corte, fila.mes), monto + comision, d["acreedor"]))
    return salida

"""Endpoints de los apartados Proyecciones, Impuestos y Deudas. Todos filtran por la empresa autorizada."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import update

from app.alerts.redaccion import redactar
from app.alerts.reglas import Alerta
from app.api.deps import Conn, EmpresaEditable, EmpresaId
from app.chat.apartados import explicar
from app.db import models as m
from app.deudas import consultas as dq
from app.deudas import formulas as df
from app.deudas import servicio as deudas_srv
from app.finance import consultas as q
from app.impuestos import servicio as imp_srv
from app.proyecciones import servicio as proy_srv

router = APIRouter(prefix="/empresas/{id_empresa}", tags=["predictivo"])


def _semanas(semanas: int = Query(8, description="Horizonte del pronóstico: 4, 8 o 12 semanas")) -> int:
    if semanas not in (4, 8, 12):
        raise HTTPException(422, "Revisa estos datos: semanas.")
    return semanas


Semanas = Annotated[int, Depends(_semanas)]


def _con_ia(resultado: dict, redactar_ia: bool) -> dict:
    if redactar_ia and resultado.get("alertas"):
        resultado["alertas"] = [a.model_dump() for a in redactar([Alerta(**a) for a in resultado["alertas"]])]
    return resultado


# ------------------------------------------------------------------ Proyecciones


class EscenarioEntrada(BaseModel):
    ventas_pct: float = Field(0, ge=-0.30, le=0.30)
    precios_pct: float = Field(0, ge=-0.10, le=0.10)
    gasto_fijo_extra: float = Field(0, ge=0, le=1_000_000)
    deuda_monto: float = Field(0, ge=0, le=100_000_000)
    deuda_tasa: float = Field(0, ge=0, le=5)
    deuda_plazo: int = Field(0, ge=0, le=360)


@router.get("/proyecciones")
def proyecciones(conn: Conn, id_empresa: EmpresaId, semanas: Semanas, redactar_ia: bool = False) -> dict:
    """Pronóstico de ventas, utilidad, efectivo día por día, equilibrio, inventario y consejos."""
    return _con_ia(proy_srv.proyeccion(conn, id_empresa, semanas=semanas), redactar_ia)


@router.post("/proyecciones/escenario")
def escenario(datos: EscenarioEntrada, conn: Conn, id_empresa: EmpresaId, semanas: Semanas) -> dict:
    """¿Qué pasa si…? Recalcula todo con los cambios indicados (no guarda nada)."""
    esc = proy_srv.Escenario(**datos.model_dump())
    return proy_srv.proyeccion(conn, id_empresa, esc, semanas)


@router.get("/proyecciones/clara")
def clara_proyecciones(conn: Conn, id_empresa: EmpresaId) -> dict:
    r = proy_srv.proyeccion(conn, id_empresa)
    return explicar(proy_srv.datos_para_clara(r), proy_srv.plantilla_clara(r))


class ProductoFiscalEntrada(BaseModel):
    tasa_iva: float | None = Field(None, ge=0, le=0.16)
    lead_time_dias: int | None = Field(None, ge=0, le=90)
    empaque: float | None = Field(None, gt=0, le=10000)


@router.patch("/productos/{id_producto}/parametros")
def producto_parametros(id_producto: int, datos: ProductoFiscalEntrada, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    """Tasa de IVA (0 % o 16 %), días de entrega del proveedor y empaque de un producto."""
    campos = datos.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(422, "No enviaste ningún dato para cambiar.")
    r = conn.execute(update(m.productos_cat).where(m.productos_cat.c.id_empresa == id_empresa,
                                                   m.productos_cat.c.id_producto == id_producto).values(**campos))
    if r.rowcount == 0:
        raise HTTPException(404, "Ese producto no existe en tu negocio.")
    return {"ok": True}


# ------------------------------------------------------------------ Impuestos


class ConfiguracionFiscal(BaseModel):
    tipo_persona: Literal["fisica", "moral"]
    regimen: Literal["626", "612", "601"]
    factura_a_morales: bool = False
    pct_ventas_morales: float = Field(0, ge=0, le=1)
    tiene_trabajadores: bool = False
    coeficiente_utilidad: float = Field(0.2, ge=0, le=1)
    minimo_seguridad: float | None = Field(None, ge=0)
    fondo_emergencia: float | None = Field(None, ge=0)


TEXTO_REGIMEN = {"626": "RESICO", "612": "Persona Física con Actividad Empresarial", "601": "General de Ley"}


@router.get("/impuestos")
def impuestos(conn: Conn, id_empresa: EmpresaId, mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$")) -> dict:
    ref = date.fromisoformat(f"{mes}-01") if mes else None
    return imp_srv.calcular(conn, id_empresa, ref)


@router.get("/impuestos/gastos")
def impuestos_gastos(conn: Conn, id_empresa: EmpresaId, mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$")) -> list[dict]:
    """"¿Esto se puede deducir?": cada gasto del mes con su clasificación y el motivo."""
    ref = date.fromisoformat(f"{mes}-01") if mes else None
    return imp_srv.gastos_clasificados(conn, id_empresa, ref)


@router.get("/impuestos/clara")
def clara_impuestos(conn: Conn, id_empresa: EmpresaId) -> dict:
    r = imp_srv.calcular(conn, id_empresa)
    return explicar(imp_srv.datos_para_clara(r), imp_srv.plantilla_clara(r))


@router.put("/impuestos/configuracion")
def guardar_configuracion(datos: ConfiguracionFiscal, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    if datos.tipo_persona == "moral" and datos.regimen != "601":
        raise HTTPException(422, "Una persona moral tributa en el régimen General de Ley (601).")
    if datos.tipo_persona == "fisica" and datos.regimen == "601":
        raise HTTPException(422, "El régimen General de Ley (601) es para personas morales.")
    valores = {
        "tipo_persona": datos.tipo_persona, "regimen_fiscal": TEXTO_REGIMEN[datos.regimen],
        "factura_a_morales": datos.factura_a_morales, "pct_ventas_morales": datos.pct_ventas_morales if datos.factura_a_morales else 0,
        "tiene_trabajadores": datos.tiene_trabajadores, "coeficiente_utilidad": datos.coeficiente_utilidad,
    }
    if datos.minimo_seguridad is not None:
        valores["minimo_seguridad"] = datos.minimo_seguridad
    if datos.fondo_emergencia is not None:
        valores["fondo_emergencia"] = datos.fondo_emergencia
    conn.execute(update(m.empresas).where(m.empresas.c.id_empresa == id_empresa).values(**valores))
    return imp_srv.configuracion(conn, id_empresa)


class GastoFiscalEntrada(BaseModel):
    tiene_cfdi: bool | None = None
    medio_pago: Literal["efectivo", "transferencia", "tarjeta", "cheque"] | None = None
    uso: Literal["negocio", "personal"] | None = None


@router.patch("/gastos/{id_gasto}/fiscal")
def gasto_fiscal(id_gasto: int, datos: GastoFiscalEntrada, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    """Corrige si un gasto tiene factura, cómo se pagó y si es del negocio (cambia lo que se puede deducir)."""
    campos = datos.model_dump(exclude_unset=True, exclude_none=True)
    if not campos:
        raise HTTPException(422, "No enviaste ningún dato para cambiar.")
    r = conn.execute(update(m.gastos_operativos).where(m.gastos_operativos.c.id_empresa == id_empresa,
                                                       m.gastos_operativos.c.id_gasto == id_gasto).values(**campos))
    if r.rowcount == 0:
        raise HTTPException(404, "No encontramos ese gasto en tu negocio.")
    return {"ok": True}


# ------------------------------------------------------------------ Deudas


class DeudaEntrada(BaseModel):
    acreedor: str = Field(min_length=1, max_length=120)
    tipo: Literal["tarjeta_credito", "credito_simple", "credito_revolvente", "proveedor", "prestamo_personal", "arrendamiento"]
    monto_original: float = Field(0, ge=0, le=100_000_000)
    saldo_actual: float = Field(ge=0, le=100_000_000)
    tasa_interes_anual: float = Field(0, ge=0, le=5, description="Fracción: 0.54 = 54 %")
    cat: float | None = Field(None, ge=0, le=10)
    aplica_iva_intereses: bool | None = None
    plazo_meses: int | None = Field(None, ge=1, le=600)
    pago_mensual: float | None = Field(None, ge=0, le=100_000_000)
    limite_credito: float | None = Field(None, ge=0, le=100_000_000)
    fecha_inicio: date
    dia_corte: int | None = Field(None, ge=1, le=31)
    dia_limite_pago: int | None = Field(None, ge=1, le=31)
    comisiones_mensuales: float = Field(0, ge=0, le=1_000_000)
    tasa_moratoria_anual: float | None = Field(None, ge=0, le=10)
    uso: Literal["negocio", "personal"] = "negocio"
    estado: Literal["activa", "liquidada", "vencida"] = "activa"

    def valores(self) -> dict:
        v = self.model_dump()
        if v["aplica_iva_intereses"] is None:       # por defecto, tarjetas y créditos bancarios cobran IVA sobre intereses
            v["aplica_iva_intereses"] = self.tipo in ("tarjeta_credito", "credito_simple", "credito_revolvente") and self.tasa_interes_anual > 0
        return v


class PagoEntrada(BaseModel):
    fecha: date
    monto: float = Field(gt=0, le=100_000_000)


def _deuda_o_404(conn: Conn, id_empresa: int, id_deuda: int) -> dict:
    d = dq.obtener(conn, id_empresa, id_deuda)
    if d is None:
        raise HTTPException(404, "No encontramos esa deuda en tu negocio.")
    return d


@router.get("/deudas")
def deudas(conn: Conn, id_empresa: EmpresaId, extra: float | None = Query(None, ge=0, le=10_000_000), redactar_ia: bool = False) -> dict:
    """Panel de deudas: tarjetas, indicadores, estrategias avalancha / bola de nieve y gráficas."""
    return _con_ia(deudas_srv.panel(conn, id_empresa, extra), redactar_ia)


@router.get("/deudas/clara")
def clara_deudas(conn: Conn, id_empresa: EmpresaId) -> dict:
    r = deudas_srv.panel(conn, id_empresa)
    return explicar(deudas_srv.datos_para_clara(r), deudas_srv.plantilla_clara(r))


@router.post("/deudas", status_code=201)
def crear_deuda(datos: DeudaEntrada, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    return {"id_deuda": dq.crear(conn, id_empresa, datos.valores())}


@router.put("/deudas/{id_deuda}")
def editar_deuda(id_deuda: int, datos: DeudaEntrada, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    if not dq.actualizar(conn, id_empresa, id_deuda, datos.valores()):
        raise HTTPException(404, "No encontramos esa deuda en tu negocio.")
    return {"ok": True}


@router.delete("/deudas/{id_deuda}")
def borrar_deuda(id_deuda: int, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    if not dq.eliminar(conn, id_empresa, id_deuda):
        raise HTTPException(404, "No encontramos esa deuda en tu negocio.")
    return {"ok": True}


@router.post("/deudas/{id_deuda}/liquidar")
def liquidar_deuda(id_deuda: int, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    _deuda_o_404(conn, id_empresa, id_deuda)
    dq.actualizar(conn, id_empresa, id_deuda, {"saldo_actual": 0, "estado": "liquidada"})
    return {"ok": True}


@router.post("/deudas/{id_deuda}/pagos", status_code=201)
def abonar(id_deuda: int, datos: PagoEntrada, conn: Conn, id_empresa: EmpresaEditable) -> dict:
    """Registra un abono: se aplica primero a IVA e intereses del mes y el resto baja el capital."""
    d = _deuda_o_404(conn, id_empresa, id_deuda)
    if d["estado"] == "liquidada":
        raise HTTPException(422, "Esa deuda ya está liquidada.")
    return dq.registrar_pago(conn, id_empresa, d, datos.fecha, datos.monto)


@router.get("/deudas/{id_deuda}/pagos")
def historial_pagos(id_deuda: int, conn: Conn, id_empresa: EmpresaId) -> list[dict]:
    _deuda_o_404(conn, id_empresa, id_deuda)
    return [{**p, "monto": float(p["monto"]), "capital": float(p["capital"]), "interes": float(p["interes"]), "iva": float(p["iva"]),
             "fecha": p["fecha"].isoformat()} for p in dq.pagos(conn, id_empresa, id_deuda)]


@router.get("/deudas/{id_deuda}/amortizacion")
def amortizacion(id_deuda: int, conn: Conn, id_empresa: EmpresaId) -> list[dict]:
    d = _deuda_o_404(conn, id_empresa, id_deuda)
    corte = q.rango_datos(conn, id_empresa)[1] or date.today()
    return deudas_srv.tabla_amortizacion(d, corte)


@router.get("/deudas/{id_deuda}/ahorro")
def ahorro_extra(id_deuda: int, conn: Conn, id_empresa: EmpresaId, extra: float = Query(gt=0, le=10_000_000)) -> dict:
    """Cuánto interés y cuántos meses te ahorras si abonas `extra` pesos más cada mes."""
    d = _deuda_o_404(conn, id_empresa, id_deuda)
    corte = q.rango_datos(conn, id_empresa)[1] or date.today()
    return df.ahorro_pago_extra(dq.a_sim(d, corte), extra)


@router.get("/deudas/simulador/pago")
def simulador_pago(conn: Conn, id_empresa: EmpresaId, saldo: float = Query(gt=0, le=100_000_000), tasa: float = Query(ge=0, le=5),
                   pago: float = Query(gt=0, le=100_000_000), con_iva: bool = True) -> dict:
    """¿En cuánto tiempo termino de pagar con este pago? Avisa si la deuda nunca baja."""
    meses = df.meses_para_liquidar(saldo, tasa, pago, con_iva)
    return {"nunca_baja": meses is None, "meses": None if meses is None else round(meses, 1)}

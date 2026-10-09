"""Endpoints del panel: resumen, finanzas, productos, flujo, pronóstico y alertas."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import update

from app.alerts.reglas import Alerta, evaluar, umbrales_empresa
from app.alerts.redaccion import redactar
from app.api.deps import Conn, EmpresaEditable, EmpresaId, Periodo
from app.config import UmbralesAlerta
from app.db import models as m
from app.finance import consultas as q
from app.finance import esquemas as e
from app.finance import servicio
from app.forecasting.servicio import completar_dias, get_forecast_service
from app.inicio import servicio as inicio_srv

router = APIRouter(prefix="/empresas/{id_empresa}", tags=["panel"])


class InfoEmpresa(BaseModel):
    id_empresa: int
    nombre_negocio: str
    giro: str
    ciudad: str | None
    regimen_fiscal: str | None
    primer_dato: str | None
    ultimo_dato: str | None
    tiene_datos: bool
    umbrales: UmbralesAlerta


@router.get("", response_model=InfoEmpresa)
def info(conn: Conn, id_empresa: EmpresaId) -> InfoEmpresa:
    emp = q.empresa(conn, id_empresa)
    primero, ultimo = q.rango_datos(conn, id_empresa)
    return InfoEmpresa(
        id_empresa=id_empresa, nombre_negocio=emp["nombre_negocio"], giro=emp["giro"], ciudad=emp["ciudad"],
        regimen_fiscal=emp["regimen_fiscal"], primer_dato=primero.isoformat() if primero else None,
        ultimo_dato=ultimo.isoformat() if ultimo else None, tiene_datos=primero is not None,
        umbrales=umbrales_empresa(conn, id_empresa),
    )


class UmbralesEntrada(BaseModel):
    margen_neto_bajo: float = Field(ge=0, le=1)
    margen_producto_bajo: float = Field(ge=0, le=1)
    dias_inventario_bajo: float = Field(ge=0, le=90)
    gastos_vs_ventas_pp: float = Field(ge=0, le=1)
    caida_ventas: float = Field(ge=0, le=1)
    subida_costo: float = Field(ge=0, le=1)
    buena_rentabilidad: float = Field(ge=0, le=1)
    crecimiento_ventas: float = Field(ge=0, le=1)


@router.put("/umbrales", response_model=UmbralesAlerta)
def guardar_umbrales(datos: UmbralesEntrada, conn: Conn, id_empresa: EmpresaEditable) -> UmbralesAlerta:
    conn.execute(update(m.empresas).where(m.empresas.c.id_empresa == id_empresa)
                 .values(umbrales_alerta=datos.model_dump()))
    return umbrales_empresa(conn, id_empresa)


@router.get("/inicio", response_model=inicio_srv.Inicio)
def inicio(conn: Conn, id_empresa: EmpresaId) -> inicio_srv.Inicio:
    """Inicio sencillo: pocas cifras, ya calculadas por los servicios del modo avanzado."""
    return inicio_srv.inicio(conn, id_empresa)


@router.get("/resumen", response_model=e.Resumen)
def resumen(conn: Conn, id_empresa: EmpresaId, periodo: Periodo) -> e.Resumen:
    return servicio.resumen(conn, id_empresa, *periodo)


@router.get("/serie", response_model=list[e.PuntoSerie])
def serie(conn: Conn, id_empresa: EmpresaId, periodo: Periodo,
          granularidad: Literal["dia", "semana", "mes"] = "dia") -> list[e.PuntoSerie]:
    return servicio.serie(conn, id_empresa, *periodo, granularidad)


@router.get("/finanzas", response_model=e.Finanzas)
def finanzas(conn: Conn, id_empresa: EmpresaId, periodo: Periodo) -> e.Finanzas:
    return servicio.finanzas(conn, id_empresa, *periodo)


@router.get("/productos", response_model=e.Productos)
def productos(conn: Conn, id_empresa: EmpresaId, periodo: Periodo) -> e.Productos:
    u = umbrales_empresa(conn, id_empresa)
    return servicio.productos(conn, id_empresa, *periodo, u.dias_inventario_bajo)


@router.get("/flujo", response_model=e.Flujo)
def flujo(conn: Conn, id_empresa: EmpresaId, periodo: Periodo) -> e.Flujo:
    return servicio.flujo(conn, id_empresa, *periodo)


class PuntoValor(BaseModel):
    fecha: str
    valor: float


class PuntoPronostico(PuntoValor):
    inferior: float
    superior: float


class Pronostico(BaseModel):
    metodo: str
    serie: str
    id_producto: int | None
    dias: int
    historico: list[PuntoValor]
    pronostico: list[PuntoPronostico]
    total_pronosticado: float


@router.get("/forecast", response_model=Pronostico)
def forecast(conn: Conn, id_empresa: EmpresaId, serie: Literal["ventas", "unidades"] = "ventas",
             id_producto: int | None = None, dias: int = Query(30, ge=7, le=90)) -> Pronostico:
    """Pronóstico diario. Fase 1: promedio móvil. Fase 2: Prophet/ARIMA con la misma respuesta."""
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        raise HTTPException(404, "Aún no hay ventas para pronosticar. Sube tu primer Excel.")
    desde = corte - timedelta(days=89)
    if id_producto is not None:
        if id_producto not in {p["id_producto"] for p in q.productos(conn, id_empresa)}:
            raise HTTPException(404, "Ese producto no existe en tu negocio.")
        filas = q.serie_producto(conn, id_empresa, id_producto, desde, corte)
        puntos = [(f["fecha"], f["unidades"] if serie == "unidades" else f["ingreso"]) for f in filas]
    else:
        filas = q.ventas_diarias(conn, id_empresa, desde, corte)
        puntos = [(f["fecha"], f["unidades"] if serie == "unidades" else f["ingreso"]) for f in filas]
    historico = completar_dias(puntos, desde, corte)
    servicio_f = get_forecast_service()
    futuro = servicio_f.pronosticar(historico, dias)
    return Pronostico(
        metodo=servicio_f.metodo, serie=serie, id_producto=id_producto, dias=dias,
        historico=[PuntoValor(fecha=p.fecha.isoformat(), valor=p.valor) for p in historico],
        pronostico=[PuntoPronostico(fecha=p.fecha.isoformat(), valor=p.valor, inferior=p.inferior, superior=p.superior)
                    for p in futuro],
        total_pronosticado=round(sum(p.valor for p in futuro), 2),
    )


@router.get("/alertas", response_model=list[Alerta])
def alertas(conn: Conn, id_empresa: EmpresaId, periodo: Periodo, redactar_ia: bool = False) -> list[Alerta]:
    lista = evaluar(conn, id_empresa, *periodo)
    return redactar(lista) if redactar_ia else lista

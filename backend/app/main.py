"""Aplicación FastAPI. Ejecutar desde backend/:  uvicorn app.main:app --reload"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api import rutas_auth, rutas_chat, rutas_empresas, rutas_equipo, rutas_ingesta, rutas_predictivo
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Cuentas Claras API",
    description="Inteligencia financiera para tiendas pequeñas. El código calcula, la IA explica.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origenes,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (rutas_auth.router, rutas_empresas.router, rutas_chat.router, rutas_ingesta.router, rutas_predictivo.router,
               rutas_equipo.router):
    app.include_router(router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def error_validacion(_: Request, error: RequestValidationError) -> JSONResponse:
    campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
    return JSONResponse(status_code=422, content={"detail": f"Revisa estos datos: {campos}."})


@app.exception_handler(OperationalError)
async def error_bd(_: Request, __: OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "No pudimos conectar con la base de datos. Intenta en un momento."})


@app.get("/api/salud", tags=["sistema"])
def salud() -> dict:
    return {"estado": "ok"}

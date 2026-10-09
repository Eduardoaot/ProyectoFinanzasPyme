"""Chat con Clara (respuesta completa o en streaming NDJSON) y estado de la IA."""

import json
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import Conn, EmpresaId, Usuario
from app.chat.asistente import ChatRespuesta, responder, responder_stream
from app.db.session import get_engine
from app.llm.ollama import get_llm

router = APIRouter(tags=["chat"])


class Pregunta(BaseModel):
    mensaje: str = Field(min_length=1, max_length=500)
    desde: date | None = None
    hasta: date | None = None
    intencion_anterior: str | None = None
    # Inicio sencillo: para quien no conoce ningún término de negocio (palabras de todos los días).
    sencillo: bool = False
    # False = solo el texto del sistema (instantáneo y siempre correcto); la IA queda para "otras palabras".
    usar_ia: bool = True


@router.post("/empresas/{id_empresa}/chat", response_model=ChatRespuesta)
def chat(pregunta: Pregunta, conn: Conn, id_empresa: EmpresaId) -> ChatRespuesta:
    """Devuelve {"answer": "...", ...}: cifras del código + interpretación de la IA."""
    return responder(conn, id_empresa, pregunta.mensaje, pregunta.desde, pregunta.hasta, pregunta.intencion_anterior,
                     sencillo=pregunta.sencillo, usar_ia=pregunta.usar_ia)


@router.post("/empresas/{id_empresa}/chat/stream")
def chat_stream(pregunta: Pregunta, id_empresa: EmpresaId) -> StreamingResponse:
    """Eventos NDJSON: inicio (cifras) → token (texto de la IA) → final (respuesta validada)."""

    def eventos() -> Iterator[str]:
        # Conexión propia: la del request se cierra antes de que termine el streaming.
        with get_engine().connect() as conn:
            for evento in responder_stream(conn, id_empresa, pregunta.mensaje, pregunta.desde, pregunta.hasta,
                                           pregunta.intencion_anterior, sencillo=pregunta.sencillo,
                                           usar_ia=pregunta.usar_ia):
                yield json.dumps(evento, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(eventos(), media_type="application/x-ndjson")


@router.get("/ia/estado")
def estado_ia(_: Usuario) -> dict:
    return get_llm().estado()

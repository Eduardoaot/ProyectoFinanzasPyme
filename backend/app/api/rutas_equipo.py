"""Quién puede ver cada negocio: el dueño invita (rol 'consulta') o quita acceso a otras cuentas.

Solo se puede invitar a cuentas que ya existen (decisión del 2026-10-09): no hay invitaciones
pendientes ni envío de correos. Todas las rutas exigen ser dueño del negocio (CLAUDE.md §8).

Un dueño puede volver dueño a un invitado y también regresarlo a "solo ver"; lo único que no puede
es cambiar o quitar su propio acceso. Así el negocio siempre conserva al menos un dueño.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import case, delete, insert, select, update

from app.api.deps import Conn, EmpresaEditable, Usuario
from app.db import models as m

router = APIRouter(prefix="/empresas/{id_empresa}/accesos", tags=["equipo"])


class Acceso(BaseModel):
    id_usuario: int
    nombre: str
    email: str
    rol: Literal["dueno", "consulta"]
    eres_tu: bool


class Invitacion(BaseModel):
    email: EmailStr


class CambioRol(BaseModel):
    rol: Literal["dueno", "consulta"]


def _rol_de_otro(conn, id_empresa: int, id_usuario: int, usuario_actual: dict) -> str:
    """Rol de otra persona en el negocio; nadie cambia ni quita su propio acceso."""
    if id_usuario == usuario_actual["id_usuario"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No puedes cambiar ni quitar tu propio acceso. Pídeselo a otro dueño del negocio.")
    rol = conn.execute(select(m.usuarios_empresas.c.rol).where(
        m.usuarios_empresas.c.id_usuario == id_usuario,
        m.usuarios_empresas.c.id_empresa == id_empresa,
    )).scalar()
    if rol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa persona no tiene acceso a este negocio.")
    return rol


def _accesos(conn, id_empresa: int, id_usuario_actual: int) -> list[Acceso]:
    filas = conn.execute(
        select(m.usuarios.c.id_usuario, m.usuarios.c.nombre, m.usuarios.c.email, m.usuarios_empresas.c.rol)
        .join(m.usuarios_empresas, m.usuarios_empresas.c.id_usuario == m.usuarios.c.id_usuario)
        .where(m.usuarios_empresas.c.id_empresa == id_empresa)
        .order_by(case((m.usuarios_empresas.c.rol == "dueno", 0), else_=1), m.usuarios.c.nombre)   # dueños primero
    ).mappings()
    return [Acceso(**f, eres_tu=f["id_usuario"] == id_usuario_actual) for f in filas]


@router.get("", response_model=list[Acceso])
def listar(conn: Conn, usuario: Usuario, id_empresa: EmpresaEditable) -> list[Acceso]:
    return _accesos(conn, id_empresa, usuario["id_usuario"])


@router.post("", response_model=Acceso, status_code=status.HTTP_201_CREATED)
def invitar(datos: Invitacion, conn: Conn, usuario: Usuario, id_empresa: EmpresaEditable) -> Acceso:
    invitado = conn.execute(select(m.usuarios.c.id_usuario, m.usuarios.c.nombre, m.usuarios.c.email)
                            .where(m.usuarios.c.email == datos.email.lower())).mappings().first()
    if invitado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No hay ninguna cuenta con ese correo. Pídele que se registre primero "
                            "(puede elegir «Soy contador») y vuelve a invitarlo.")
    ya = conn.execute(select(m.usuarios_empresas.c.rol).where(
        m.usuarios_empresas.c.id_usuario == invitado["id_usuario"],
        m.usuarios_empresas.c.id_empresa == id_empresa,
    )).first()
    if ya is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa persona ya tiene acceso a este negocio.")
    conn.execute(insert(m.usuarios_empresas).values(
        id_usuario=invitado["id_usuario"], id_empresa=id_empresa, rol="consulta"))
    return Acceso(**invitado, rol="consulta", eres_tu=False)


@router.patch("/{id_usuario}", response_model=Acceso)
def cambiar_rol(datos: CambioRol, conn: Conn, usuario: Usuario, id_empresa: EmpresaEditable,
                id_usuario: int = Path(ge=1)) -> Acceso:
    _rol_de_otro(conn, id_empresa, id_usuario, usuario)
    conn.execute(update(m.usuarios_empresas).where(
        m.usuarios_empresas.c.id_usuario == id_usuario,
        m.usuarios_empresas.c.id_empresa == id_empresa,
    ).values(rol=datos.rol))
    return next(a for a in _accesos(conn, id_empresa, usuario["id_usuario"]) if a.id_usuario == id_usuario)


@router.delete("/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
def quitar(conn: Conn, usuario: Usuario, id_empresa: EmpresaEditable, id_usuario: int = Path(ge=1)) -> Response:
    _rol_de_otro(conn, id_empresa, id_usuario, usuario)
    conn.execute(delete(m.usuarios_empresas).where(
        m.usuarios_empresas.c.id_usuario == id_usuario,
        m.usuarios_empresas.c.id_empresa == id_empresa,
    ))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

# Valores fijos, ya sembrados en 0004_seed_roles.py -- no se crea un
# endpoint solo para exponer estos 3 nombres.
RolNombre = Literal["admin", "contador", "consulta"]


class UsuarioEmpresaCreate(BaseModel):
    """Si `email` ya existe como Usuario, solo se vincula a la empresa
    activa con el rol dado (nombre_completo/password se ignoran). Si
    no existe, se crea el Usuario -- nombre_completo y password pasan
    a ser obligatorios."""

    email: EmailStr
    rol: RolNombre
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=200)
    # Auditoría de seguridad 2026-08-25 (hallazgo B1): ver nota en
    # schemas/auth.py::CambiarPasswordTemporalRequest.
    password: str | None = Field(default=None, min_length=10)

    @model_validator(mode="after")
    def _validar_datos_de_usuario_nuevo(self) -> "UsuarioEmpresaCreate":
        # No se puede saber aquí si el email ya existe en BD (eso lo
        # resuelve el servicio) -- si YA se mandaron ambos campos está
        # bien de cualquier forma; si falta alguno, se deja pasar y el
        # servicio exige explícitamente ambos cuando el usuario es
        # nuevo, con un mensaje más útil que un 422 genérico de schema.
        return self


class UsuarioEmpresaUpdate(BaseModel):
    rol: RolNombre | None = None
    activo: bool | None = None


class UsuarioEmpresaOut(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    email: str
    nombre_completo: str
    rol: str
    activo: bool
    created_at: datetime.datetime

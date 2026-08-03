import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoIdentificacion = Literal["cedula", "pasaporte"]
EstadoEmpleado = Literal["activo", "inactivo"]


class EmpleadoBase(BaseModel):
    tipo_identificacion: TipoIdentificacion = "cedula"
    identificacion: str = Field(min_length=1, max_length=30)
    nombre_completo: str = Field(min_length=1, max_length=200)
    fecha_nacimiento: datetime.date | None = None
    fecha_nacionalidad: str | None = Field(default=None, max_length=50)
    email_personal: str | None = Field(default=None, max_length=150)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = None
    numero_seguro_social: str | None = Field(default=None, max_length=30)


class EmpleadoCreate(EmpleadoBase):
    """empresa_id NUNCA viene del cliente: sale de la empresa activa del
    JWT (ver core/deps.get_empresa_activa_id), igual que en /auth."""


class EmpleadoUpdate(BaseModel):
    tipo_identificacion: TipoIdentificacion | None = None
    identificacion: str | None = Field(default=None, min_length=1, max_length=30)
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=200)
    fecha_nacimiento: datetime.date | None = None
    fecha_nacionalidad: str | None = Field(default=None, max_length=50)
    email_personal: str | None = Field(default=None, max_length=150)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = None
    numero_seguro_social: str | None = Field(default=None, max_length=30)
    estado: EstadoEmpleado | None = None


class EmpleadoOut(EmpleadoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

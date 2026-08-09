import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

TipoIdentificacion = Literal["cedula", "pasaporte"]
EstadoEmpleado = Literal["activo", "inactivo"]
Sexo = Literal["masculino", "femenino", "otro"]


class EmpleadoBase(BaseModel):
    tipo_identificacion: TipoIdentificacion = "cedula"
    identificacion: str = Field(min_length=1, max_length=30)
    nombre_completo: str = Field(min_length=1, max_length=200)
    fecha_nacimiento: datetime.date | None = None
    nacionalidad: str | None = Field(default=None, max_length=50)
    sexo: Sexo | None = None
    email_personal: str | None = Field(default=None, max_length=150)
    codigo_pais: str | None = Field(default=None, max_length=5)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = None
    numero_seguro_social: str | None = Field(default=None, max_length=30)
    padece_enfermedad: bool = False
    detalle_enfermedad: str | None = None


class EmpleadoCreate(EmpleadoBase):
    """empresa_id NUNCA viene del cliente: sale de la empresa activa del
    JWT (ver core/deps.get_empresa_activa_id), igual que en /auth."""


class EmpleadoUpdate(BaseModel):
    """identificacion, nombre_completo y email_personal NO están acá a
    propósito -- son datos de identidad legal, inmutables una vez creado
    el empleado (confirmado explícitamente por el usuario). El PATCH los
    ignora aunque alguien los mande por API, porque
    empleados_service.actualizar_empleado aplica los cambios vía
    model_dump(exclude_unset=True) sobre este schema. Los documentos
    tampoco están acá: se suben aparte por multipart, igual que el logo
    de empresa no está en EmpresaUpdate."""

    fecha_nacimiento: datetime.date | None = None
    nacionalidad: str | None = Field(default=None, max_length=50)
    sexo: Sexo | None = None
    codigo_pais: str | None = Field(default=None, max_length=5)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = None
    numero_seguro_social: str | None = Field(default=None, max_length=30)
    padece_enfermedad: bool | None = None
    detalle_enfermedad: str | None = None
    estado: EstadoEmpleado | None = None


class EmpleadoOut(EmpleadoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # Nunca el binario inline acá (bloatearía cada fetch de empleado) --
    # mismo patrón que EmpresaOut.logo. El binario se sirve aparte vía
    # GET /empleados/{id}/documento-identificacion o .../documento-
    # certificado-medico.
    documento_identificacion: bytes | None = Field(default=None, exclude=True, repr=False)
    documento_identificacion_nombre_archivo: str | None = None
    documento_certificado_medico: bytes | None = Field(default=None, exclude=True, repr=False)
    documento_certificado_medico_nombre_archivo: str | None = None

    @computed_field
    @property
    def tiene_documento_identificacion(self) -> bool:
        return self.documento_identificacion is not None

    @computed_field
    @property
    def tiene_documento_certificado_medico(self) -> bool:
        return self.documento_certificado_medico is not None

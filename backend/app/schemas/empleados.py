import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

TipoIdentificacion = Literal["cedula", "pasaporte"]
EstadoEmpleado = Literal["activo", "inactivo"]
Sexo = Literal["masculino", "femenino", "otro"]

EDAD_MINIMA_ANOS = 18


def _validar_mayor_edad(fecha: datetime.date | None) -> datetime.date | None:
    """Panamá: mayoría de edad a los 18 años (Código Civil). Se calcula
    contra la fecha de hoy en cada validación, nunca contra un año
    fijo, para que la regla siga siendo correcta con el paso del tiempo."""
    if fecha is None:
        return fecha
    hoy = datetime.date.today()
    edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
    if edad < EDAD_MINIMA_ANOS:
        raise ValueError(
            f"El empleado debe ser mayor de edad ({EDAD_MINIMA_ANOS} años o más) para poder registrarse."
        )
    return fecha


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
    direccion: str | None = Field(default=None, max_length=500)
    numero_seguro_social: str | None = Field(default=None, max_length=30)
    padece_enfermedad: bool = False
    detalle_enfermedad: str | None = Field(default=None, max_length=1000)


class EmpleadoCreate(EmpleadoBase):
    """empresa_id NUNCA viene del cliente: sale de la empresa activa del
    JWT (ver core/deps.get_empresa_activa_id), igual que en /auth."""

    @field_validator("fecha_nacimiento")
    @classmethod
    def _validar_fecha_nacimiento(cls, v: datetime.date | None) -> datetime.date | None:
        return _validar_mayor_edad(v)


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
    direccion: str | None = Field(default=None, max_length=500)
    numero_seguro_social: str | None = Field(default=None, max_length=30)
    padece_enfermedad: bool | None = None
    detalle_enfermedad: str | None = Field(default=None, max_length=1000)
    estado: EstadoEmpleado | None = None

    @field_validator("fecha_nacimiento")
    @classmethod
    def _validar_fecha_nacimiento(cls, v: datetime.date | None) -> datetime.date | None:
        return _validar_mayor_edad(v)


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

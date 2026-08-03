import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoContrato = Literal["indefinido", "definido", "obra_determinada"]
PeriodicidadPago = Literal["quincenal", "mensual"]
EstadoContrato = Literal["vigente", "terminado"]


class ContratoCreate(BaseModel):
    """empresa_id NUNCA viene del cliente (sale de la empresa activa del
    JWT). El salario inicial se manda aquí para poder abrir el primer
    registro de historial_salarial junto con el contrato."""

    tipo_contrato: TipoContrato
    cargo: str = Field(min_length=1, max_length=150)
    departamento: str | None = Field(default=None, max_length=150)
    fecha_inicio: datetime.date
    fecha_fin_pactada: datetime.date | None = None
    jornada_horas_semana: decimal.Decimal = Field(default=decimal.Decimal("48"), gt=0)
    periodicidad_pago: PeriodicidadPago = "quincenal"
    fecha_registro_mitradel: datetime.date | None = None
    salario_base: decimal.Decimal = Field(gt=0)


class ContratoUpdate(BaseModel):
    """Nunca incluye salario: eso solo se cambia vía POST
    /contratos/{id}/salario, para no poder pisar el historial por error."""

    cargo: str | None = Field(default=None, min_length=1, max_length=150)
    departamento: str | None = Field(default=None, max_length=150)
    fecha_fin_pactada: datetime.date | None = None
    fecha_fin_real: datetime.date | None = None
    jornada_horas_semana: decimal.Decimal | None = Field(default=None, gt=0)
    periodicidad_pago: PeriodicidadPago | None = None
    fecha_registro_mitradel: datetime.date | None = None
    estado: EstadoContrato | None = None
    motivo_terminacion: str | None = Field(default=None, max_length=50)


class ContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empleado_id: uuid.UUID
    tipo_contrato: str
    cargo: str
    departamento: str | None
    fecha_inicio: datetime.date
    fecha_fin_pactada: datetime.date | None
    fecha_fin_real: datetime.date | None
    jornada_horas_semana: decimal.Decimal
    periodicidad_pago: str
    fecha_registro_mitradel: datetime.date | None
    estado: str
    motivo_terminacion: str | None


class CambiarSalarioRequest(BaseModel):
    salario_base: decimal.Decimal = Field(gt=0)
    fecha_vigencia_desde: datetime.date
    motivo: str = Field(default="ajuste_salarial", max_length=100)


class HistorialSalarialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    salario_base: decimal.Decimal
    fecha_vigencia_desde: datetime.date
    fecha_vigencia_hasta: datetime.date | None
    motivo: str | None


class SalarioVigenteOut(BaseModel):
    contrato_id: uuid.UUID
    fecha_consulta: datetime.date
    salario_base: decimal.Decimal

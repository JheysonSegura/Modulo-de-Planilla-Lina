import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ProvisionVacacionesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    fecha_inicio_periodo: datetime.date
    dias_acumulados: decimal.Decimal
    dias_gozados: decimal.Decimal
    monto_provisionado: decimal.Decimal
    estado: str
    notificado_autoridad_trabajo: bool

    @computed_field
    @property
    def saldo_disponible(self) -> decimal.Decimal:
        return self.dias_acumulados - self.dias_gozados


class VacacionTomadaCreate(BaseModel):
    fecha: datetime.date
    dias: decimal.Decimal = Field(gt=0)


class VacacionTomadaOut(BaseModel):
    """Fase 16: historial por evento, para poder emitir boleta por cada
    toma concreta (ver app/models/provisiones.py::VacacionTomada)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provision_id: uuid.UUID
    contrato_id: uuid.UUID
    fecha: datetime.date
    dias_tomados: decimal.Decimal
    valor_dia: decimal.Decimal
    monto: decimal.Decimal
    created_at: datetime.datetime


class AcumularVacacionesRequest(BaseModel):
    fecha_acuerdo: datetime.date
    notificado_autoridad_trabajo: bool = False

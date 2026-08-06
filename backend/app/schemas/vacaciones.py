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


class AcumularVacacionesRequest(BaseModel):
    fecha_acuerdo: datetime.date
    notificado_autoridad_trabajo: bool = False

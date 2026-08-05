import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

Cuatrimestre = Literal["dic-abr", "abr-ago", "ago-dic"]


class GenerarPagoDecimoRequest(BaseModel):
    cuatrimestre: Cuatrimestre
    anio: int
    fecha_pago: datetime.date


class ProvisionDecimoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    cuatrimestre: str
    anio: int
    monto_acumulado: decimal.Decimal
    fecha_pago_programada: datetime.date
    pagado: bool
    fecha_pago_real: datetime.date | None
    movimiento_planilla_id: uuid.UUID | None

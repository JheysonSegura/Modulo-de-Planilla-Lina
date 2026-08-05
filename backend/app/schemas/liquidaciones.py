import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MotivoTerminacion = Literal[
    "renuncia_voluntaria",
    "renuncia_justificada",
    "despido_justificado",
    "despido_causa_economica",
    "despido_injustificado",
    "mutuo_acuerdo",
]


class GenerarLiquidacionRequest(BaseModel):
    motivo: MotivoTerminacion
    fecha_terminacion: datetime.date
    otras_deducciones: decimal.Decimal = Field(default=decimal.Decimal("0"), ge=0)


class LiquidacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    fecha_terminacion: datetime.date
    motivo: str
    salario_pendiente: decimal.Decimal
    decimo_proporcional: decimal.Decimal
    vacaciones_pendientes: decimal.Decimal
    prima_antiguedad: decimal.Decimal
    indemnizacion: decimal.Decimal
    preaviso: decimal.Decimal
    otras_deducciones: decimal.Decimal
    monto_total: decimal.Decimal
    estado: str

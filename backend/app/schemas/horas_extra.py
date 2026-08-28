import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 3 bandas de recargo, ya colapsadas como en CLAUDE.md sección 5 (ver
# horas_extra_service.TIPO_HORA_A_TASA para el detalle de qué numeral
# del Art. 33 CT cubre cada una).
TipoHora = Literal["diurna", "nocturna", "prolongacion_nocturna"]
TipoDia = Literal["ordinario", "domingo_descanso", "feriado_duelo_nacional"]


class RegistroHorasExtraCreate(BaseModel):
    fecha: datetime.date
    tipo_hora: TipoHora
    tipo_dia: TipoDia = "ordinario"
    horas: decimal.Decimal = Field(gt=0, le=24)
    observaciones: str | None = Field(default=None, max_length=500)


class RegistroHorasExtraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    fecha: datetime.date
    tipo_hora: str
    tipo_dia: str
    horas: decimal.Decimal
    horas_dentro_limite: decimal.Decimal
    horas_exceso_limite: decimal.Decimal
    valor_hora_ordinaria: decimal.Decimal
    factor_tipo_hora: decimal.Decimal
    factor_tipo_dia: decimal.Decimal
    factor_exceso_limite: decimal.Decimal
    monto_dentro_limite: decimal.Decimal
    monto_exceso_limite: decimal.Decimal
    monto_calculado: decimal.Decimal
    observaciones: str | None
    aplicado: bool

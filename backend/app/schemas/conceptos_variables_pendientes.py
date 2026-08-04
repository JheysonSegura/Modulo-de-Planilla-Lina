import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoConceptoVariable = Literal["ingreso", "deduccion"]


class ConceptoVariablePendienteCreate(BaseModel):
    fecha: datetime.date
    tipo: TipoConceptoVariable
    codigo: str = Field(min_length=1, max_length=50)
    descripcion: str | None = Field(default=None, max_length=500)
    monto: decimal.Decimal = Field(gt=0)


class ConceptoVariablePendienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    fecha: datetime.date
    tipo: str
    codigo: str
    descripcion: str | None
    monto: decimal.Decimal
    aplicado: bool
    movimiento_planilla_id: uuid.UUID | None

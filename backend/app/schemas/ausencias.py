import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

TipoAusencia = Literal[
    "enfermedad_dentro_fondo",
    "enfermedad_excede_fondo",
    "embarazo",
    "riesgo_profesional",
    "huelga_legal",
    "licencia_sindical_o_estado",
    "licencia_autorizada_empleador",
    "arresto_o_prision_preventiva",
    "injustificada",
]


class AusenciaCreate(BaseModel):
    tipo: TipoAusencia
    fecha_desde: datetime.date
    fecha_hasta: datetime.date
    certificado_ref: str | None = None

    @model_validator(mode="after")
    def _validar_rango(self) -> "AusenciaCreate":
        if self.fecha_hasta < self.fecha_desde:
            raise ValueError("fecha_hasta no puede ser anterior a fecha_desde.")
        return self


class AusenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    tipo: str
    fecha_desde: datetime.date
    fecha_hasta: datetime.date
    certificado_ref: str | None

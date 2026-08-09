import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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

    # Nunca el binario inline acá (bloatearía cada fetch) -- mismo patrón
    # que EmpleadoOut. El binario se sirve aparte vía GET /ausencias/{id}/documento.
    documento_constancia: bytes | None = Field(default=None, exclude=True, repr=False)
    documento_constancia_nombre_archivo: str | None = None

    @computed_field
    @property
    def tiene_documento_constancia(self) -> bool:
        return self.documento_constancia is not None

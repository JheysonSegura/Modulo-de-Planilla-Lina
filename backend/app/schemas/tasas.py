import datetime
import decimal

from pydantic import BaseModel, ConfigDict


class TasaVigenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_tasa: str
    tasa: decimal.Decimal
    fecha_inicio: datetime.date
    fecha_fin: datetime.date | None
    fuente_legal: str | None


class TramoIsrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_inicio: datetime.date
    fecha_fin: datetime.date | None
    monto_desde: decimal.Decimal
    monto_hasta: decimal.Decimal | None
    tasa_marginal: decimal.Decimal
    impuesto_base: decimal.Decimal


class TasaRiesgoProfesionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clase_riesgo: str
    tasa: decimal.Decimal
    fecha_inicio: datetime.date
    fecha_fin: datetime.date | None


class SalarioMinimoVigenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    region: str
    actividad: str | None
    tamano_empresa: str | None
    monto_hora: decimal.Decimal | None
    monto_mensual: decimal.Decimal | None
    fecha_inicio: datetime.date
    fecha_fin: datetime.date | None
    decreto_ref: str | None

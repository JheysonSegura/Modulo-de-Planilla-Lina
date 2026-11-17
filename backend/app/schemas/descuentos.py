import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

TipoDescuento = Literal[
    "prestamo_empresa",
    "prestamo_bancario",
    "hipoteca",
    "cooperativa",
    "pension_alimenticia",
    "embargo",
]
FrecuenciaDescuento = Literal["mensual", "quincenal"]


class SimularDescuentoRequest(BaseModel):
    monto_total: decimal.Decimal = Field(gt=0)
    plazo_meses: int = Field(ge=1, le=600)
    frecuencia: FrecuenciaDescuento
    fecha_inicio: datetime.date


class SimulacionDescuentoOut(BaseModel):
    numero_cuotas: int
    cuota: decimal.Decimal
    ultima_cuota: decimal.Decimal
    fecha_primera_cuota: datetime.date
    fecha_ultima_cuota: datetime.date


class DescuentoCreate(BaseModel):
    """Con monto_total + plazo_meses la cuota la calcula el sistema; sin
    ellos (pensión alimenticia, cooperativa, embargo sin deuda fija) se
    registra la cuota directamente y el descuento no termina solo."""

    tipo: TipoDescuento
    acreedor: str = Field(min_length=1, max_length=150)
    referencia: str | None = Field(default=None, max_length=100)
    monto_total: decimal.Decimal | None = Field(default=None, gt=0)
    plazo_meses: int | None = Field(default=None, ge=1, le=600)
    cuota: decimal.Decimal | None = Field(default=None, gt=0)
    frecuencia: FrecuenciaDescuento
    fecha_inicio: datetime.date
    observacion: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validar_modo(self) -> "DescuentoCreate":
        con_plazo = self.monto_total is not None or self.plazo_meses is not None
        if con_plazo and (self.monto_total is None or self.plazo_meses is None):
            raise ValueError("Indica el monto del préstamo y el plazo en meses (los dos).")
        if con_plazo and self.cuota is not None:
            raise ValueError(
                "Con monto y plazo la cuota la calcula el sistema; no la envíes también."
            )
        if not con_plazo and self.cuota is None:
            raise ValueError("Indica el monto y el plazo del préstamo, o la cuota fija.")
        return self


class CerrarDescuentoRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)
    fecha_cierre: datetime.date | None = None


class DescuentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    tipo: str
    acreedor: str
    referencia: str | None
    monto_total: decimal.Decimal | None
    plazo_meses: int | None
    frecuencia: str
    numero_cuotas: int | None
    cuota: decimal.Decimal
    fecha_inicio: datetime.date
    estado: str
    fecha_cierre: datetime.date | None
    motivo_cierre: str | None
    observacion: str | None
    created_at: datetime.datetime

    # Calculados por descuentos_service (nunca guardados).
    total_cobrado: decimal.Decimal = decimal.Decimal("0")
    saldo: decimal.Decimal | None = None
    cuotas_cobradas: int = 0
    # 'activo', 'pagado', 'cerrado' o 'terminado' (contrato liquidado).
    estado_actual: str = "activo"

    documento: bytes | None = Field(default=None, exclude=True, repr=False)
    documento_nombre_archivo: str | None = None

    @computed_field
    @property
    def tiene_documento(self) -> bool:
        return self.documento is not None


class CuotaDescuentoOut(BaseModel):
    id: uuid.UUID
    fecha_cobro: datetime.date
    monto: decimal.Decimal
    monto_programado: decimal.Decimal
    origen: str  # 'quincenal', 'mensual', 'vacaciones' o 'liquidacion'
    planilla_id: uuid.UUID | None
    liquidacion_id: uuid.UUID | None
    anulada: bool

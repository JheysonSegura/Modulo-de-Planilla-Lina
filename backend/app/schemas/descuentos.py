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

# Únicos tipos que pueden quedar sin cantidad de cuotas (decisión del usuario
# 2026-11-17): se cobran hasta que alguien los cierre.
TIPOS_SIN_FIN = {"pension_alimenticia", "cooperativa"}


class SimularDescuentoRequest(BaseModel):
    """Préstamo de la empresa: monto + plazo (el sistema calcula la cuota).
    Externo: cuota de la carta + n.º de pagos (solo se calculan fechas y total)."""

    monto_total: decimal.Decimal | None = Field(default=None, gt=0)
    plazo_meses: int | None = Field(default=None, ge=1, le=600)
    cuota: decimal.Decimal | None = Field(default=None, gt=0)
    numero_cuotas: int | None = Field(default=None, ge=1, le=1200)
    frecuencia: FrecuenciaDescuento
    fecha_inicio: datetime.date

    @model_validator(mode="after")
    def _validar_modo(self) -> "SimularDescuentoRequest":
        if not (self.monto_total and self.plazo_meses) and not (self.cuota and self.numero_cuotas):
            raise ValueError("Indica monto y plazo, o cuota y número de pagos.")
        return self


class SimulacionDescuentoOut(BaseModel):
    monto_total: decimal.Decimal
    numero_cuotas: int
    cuota: decimal.Decimal
    ultima_cuota: decimal.Decimal
    fecha_primera_cuota: datetime.date
    fecha_ultima_cuota: datetime.date


class DescuentoCreate(BaseModel):
    """Corrección del usuario 2026-11-17: solo el préstamo de la empresa se
    calcula (monto + plazo en meses -> cuota). Todo lo demás (banco,
    financiera, hipoteca, cooperativa, pensión, embargo) lleva la cuota que
    indica la carta u orden y el n.º de pagos (obligatorio, pedido del
    usuario el mismo día): con eso se detiene solo al último pago. Pensión
    alimenticia y cooperativa pueden quedar sin n.º de pagos (se cobran
    hasta que se cierren)."""

    tipo: TipoDescuento
    acreedor: str = Field(min_length=1, max_length=150)
    referencia: str | None = Field(default=None, max_length=100)
    monto_total: decimal.Decimal | None = Field(default=None, gt=0)
    plazo_meses: int | None = Field(default=None, ge=1, le=600)
    cuota: decimal.Decimal | None = Field(default=None, gt=0)
    numero_cuotas: int | None = Field(default=None, ge=1, le=1200)
    frecuencia: FrecuenciaDescuento
    fecha_inicio: datetime.date
    observacion: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validar_modo(self) -> "DescuentoCreate":
        if self.tipo == "prestamo_empresa":
            if self.monto_total is None or self.plazo_meses is None:
                raise ValueError(
                    "Préstamo de la empresa: indica el monto prestado y el plazo en meses."
                )
            if self.cuota is not None or self.numero_cuotas is not None:
                raise ValueError(
                    "Préstamo de la empresa: la cuota la calcula el sistema con el monto y el plazo."
                )
        else:
            if self.cuota is None:
                raise ValueError("Indica la cuota que se debe descontar según la carta u orden.")
            if self.numero_cuotas is None and self.tipo not in TIPOS_SIN_FIN:
                raise ValueError("Indica la cantidad de cuotas (número de pagos) que indica la carta.")
            if self.monto_total is not None or self.plazo_meses is not None:
                raise ValueError(
                    "Solo el préstamo de la empresa se calcula con monto y plazo; para este tipo "
                    "indica la cuota de la carta y el número de pagos."
                )
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

import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
    # Art. 219/220 CT: captura manual -- depende de una sentencia
    # judicial de reintegro que el sistema no puede calcular.
    monto_salarios_caidos: decimal.Decimal = Field(default=decimal.Decimal("0"), ge=0)
    referencia_sentencia: str | None = Field(default=None, max_length=100)
    # Art. 222 CT: fecha en que el trabajador notificó su renuncia (para
    # medir si el aviso previo fue suficiente). Si no se manda, NO se
    # evalúa la penalidad -- es un dato opcional que hay que capturar
    # explícitamente, ausencia de dato no implica incumplimiento.
    fecha_aviso_renuncia: datetime.date | None = None


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
    salarios_caidos: decimal.Decimal
    referencia_sentencia: str | None
    penalidad_renuncia_sin_aviso: decimal.Decimal
    monto_total: decimal.Decimal
    estado: str

    # Nunca el binario inline acá (bloatearía cada fetch) -- mismo patrón
    # que PlanillaOut. El binario se sirve aparte vía GET
    # /liquidaciones/{id}/constancia-pago.
    documento_constancia_pago: bytes | None = Field(default=None, exclude=True, repr=False)
    documento_constancia_pago_nombre_archivo: str | None = None

    @computed_field
    @property
    def tiene_constancia_pago(self) -> bool:
        return self.documento_constancia_pago is not None

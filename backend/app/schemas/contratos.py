import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoContrato = Literal["indefinido", "definido", "obra_determinada"]
PeriodicidadPago = Literal["quincenal", "mensual"]
EstadoContrato = Literal["vigente", "terminado"]


class _ExencionSalarioMinimoMixin(BaseModel):
    """Exención EXPLÍCITA (no inferida de tipo_contrato) a la validación
    de salario mínimo, para casos como pasantías formales cuyo
    tratamiento legal no está confirmado con el contador. El caso de
    medio tiempo no necesita esto: se prorratea automáticamente por
    jornada_horas_semana."""

    exento_salario_minimo: bool = False
    motivo_exencion_salario_minimo: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _requiere_motivo_si_exento(self) -> "_ExencionSalarioMinimoMixin":
        if self.exento_salario_minimo and not self.motivo_exencion_salario_minimo:
            raise ValueError(
                "motivo_exencion_salario_minimo es obligatorio cuando "
                "exento_salario_minimo es true"
            )
        return self


class ContratoCreate(_ExencionSalarioMinimoMixin):
    """empresa_id NUNCA viene del cliente (sale de la empresa activa del
    JWT). El salario inicial se manda aquí para poder abrir el primer
    registro de historial_salarial junto con el contrato."""

    tipo_contrato: TipoContrato
    cargo: str = Field(min_length=1, max_length=150)
    departamento: str | None = Field(default=None, max_length=150)
    fecha_inicio: datetime.date
    fecha_fin_pactada: datetime.date | None = None
    jornada_horas_semana: decimal.Decimal = Field(default=decimal.Decimal("48"), gt=0)
    periodicidad_pago: PeriodicidadPago = "quincenal"
    fecha_registro_mitradel: datetime.date | None = None
    salario_base: decimal.Decimal = Field(gt=0)
    es_tecnico: bool = False


class ContratoUpdate(_ExencionSalarioMinimoMixin):
    """Nunca incluye salario: eso solo se cambia vía POST
    /contratos/{id}/salario, para no poder pisar el historial por error."""

    exento_salario_minimo: bool | None = None
    cargo: str | None = Field(default=None, min_length=1, max_length=150)
    departamento: str | None = Field(default=None, max_length=150)
    fecha_fin_pactada: datetime.date | None = None
    fecha_fin_real: datetime.date | None = None
    jornada_horas_semana: decimal.Decimal | None = Field(default=None, gt=0)
    periodicidad_pago: PeriodicidadPago | None = None
    fecha_registro_mitradel: datetime.date | None = None
    estado: EstadoContrato | None = None
    motivo_terminacion: str | None = Field(default=None, max_length=50)
    es_tecnico: bool | None = None
    # La validación heredada de _ExencionSalarioMinimoMixin ya cubre este
    # campo: si queda en None (no se tocó) no exige motivo; si se manda
    # True explícitamente, sigue exigiéndolo.


class ContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    empleado_id: uuid.UUID
    tipo_contrato: str
    cargo: str
    departamento: str | None
    fecha_inicio: datetime.date
    fecha_fin_pactada: datetime.date | None
    fecha_fin_real: datetime.date | None
    jornada_horas_semana: decimal.Decimal
    periodicidad_pago: str
    fecha_registro_mitradel: datetime.date | None
    estado: str
    motivo_terminacion: str | None
    exento_salario_minimo: bool
    motivo_exencion_salario_minimo: str | None
    es_tecnico: bool


class CambiarSalarioRequest(BaseModel):
    salario_base: decimal.Decimal = Field(gt=0)
    fecha_vigencia_desde: datetime.date
    motivo: str = Field(default="ajuste_salarial", max_length=100)


class HistorialSalarialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    salario_base: decimal.Decimal
    fecha_vigencia_desde: datetime.date
    fecha_vigencia_hasta: datetime.date | None
    motivo: str | None


class SalarioVigenteOut(BaseModel):
    contrato_id: uuid.UUID
    fecha_consulta: datetime.date
    salario_base: decimal.Decimal

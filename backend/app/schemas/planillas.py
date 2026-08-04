import datetime
import decimal
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

TipoPlanilla = Literal["mensual", "quincenal"]


class GenerarPlanillaRequest(BaseModel):
    tipo: TipoPlanilla
    periodo_inicio: datetime.date
    periodo_fin: datetime.date
    fecha_pago: datetime.date

    @model_validator(mode="after")
    def _periodo_valido(self) -> "GenerarPlanillaRequest":
        if self.periodo_fin < self.periodo_inicio:
            raise ValueError("periodo_fin debe ser posterior o igual a periodo_inicio")
        return self


class PlanillaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    periodo_inicio: datetime.date
    periodo_fin: datetime.date
    fecha_pago: datetime.date
    estado: str


class ConceptoVariableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    codigo: str
    descripcion: str | None
    monto: decimal.Decimal


class MovimientoPlanillaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contrato_id: uuid.UUID
    salario_base_periodo: decimal.Decimal
    salario_bruto: decimal.Decimal
    css_empleado: decimal.Decimal
    css_patronal: decimal.Decimal
    seguro_educativo_empleado: decimal.Decimal
    seguro_educativo_patronal: decimal.Decimal
    riesgo_profesional_patronal: decimal.Decimal
    isr_retenido: decimal.Decimal
    # Auditoría del cálculo de ISR (Fase 7) -- para que el contador
    # pueda reconstruir a mano cada monto antes de validar el módulo.
    isr_renta_anual_proyectada: decimal.Decimal | None
    isr_impuesto_anual_proyectado: decimal.Decimal | None
    isr_decimo_tratamiento: str | None
    isr_numero_periodo_anio: int | None
    isr_periodos_restantes_anio: int | None
    otras_deducciones: decimal.Decimal
    salario_neto: decimal.Decimal
    conceptos_variables: list[ConceptoVariableOut] = []

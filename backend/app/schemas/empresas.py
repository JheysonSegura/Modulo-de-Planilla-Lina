import uuid

from pydantic import BaseModel, ConfigDict, Field


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    ruc: str
    clase_riesgo: str | None
    region: str | None
    actividad_economica: str | None


class EmpresaUpdate(BaseModel):
    """De momento solo expone región/actividad económica: son los campos
    que hacen falta para que salario_minimo_service pueda elegir la fila
    correcta de salario_minimo_vigente cuando hay más de una vigente."""

    region: str | None = Field(default=None, max_length=100)
    actividad_economica: str | None = Field(default=None, max_length=150)

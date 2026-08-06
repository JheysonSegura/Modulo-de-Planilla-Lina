import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class AuditoriaCambioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tabla_afectada: str
    registro_id: uuid.UUID
    empleado_id: uuid.UUID | None
    usuario_id: uuid.UUID | None
    accion: str
    datos_anteriores: dict | None
    datos_nuevos: dict | None
    created_at: datetime.datetime

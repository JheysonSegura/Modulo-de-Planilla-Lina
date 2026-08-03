import uuid

from pydantic import BaseModel, ConfigDict


class EmpleadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre_completo: str
    identificacion: str
    estado: str

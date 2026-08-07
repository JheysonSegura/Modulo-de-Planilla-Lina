import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    ruc: str
    dv: str | None
    direccion: str | None
    telefono: str | None
    clase_riesgo: str | None
    region: str | None
    actividad_economica: str | None
    tamano_empresa: str | None
    # Fase 16: nunca el binario inline acá (bloatearía cada fetch de
    # empresa) -- solo si hay que mostrar/ocultar el botón de logo en el
    # membrete. El binario se sirve aparte vía GET /empresas/actual/logo.
    logo: bytes | None = Field(default=None, exclude=True, repr=False)

    @computed_field
    @property
    def tiene_logo(self) -> bool:
        return self.logo is not None


class EmpresaUpdate(BaseModel):
    """De momento solo expone región/actividad económica/tamaño de
    empresa (para salario_minimo_service) más dv/dirección/teléfono
    (Fase 16, membrete de boletas y reportes) -- el logo se sube aparte
    vía PUT /empresas/actual/logo (multipart, no encaja en un body JSON)."""

    region: str | None = Field(default=None, max_length=100)
    actividad_economica: str | None = Field(default=None, max_length=150)
    tamano_empresa: str | None = Field(default=None, max_length=50)
    dv: str | None = Field(default=None, max_length=5)
    direccion: str | None = Field(default=None)
    telefono: str | None = Field(default=None, max_length=30)

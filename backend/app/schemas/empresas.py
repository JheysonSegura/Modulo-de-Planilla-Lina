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
    empresa (para salario_minimo_service) más ruc/dv/dirección/teléfono
    (Fase 16, membrete de recibos y reportes) -- el logo se sube aparte
    vía PUT /empresas/actual/logo (multipart, no encaja en un body JSON).

    ruc y dv son dos campos independientes en BD (columnas separadas,
    nunca combinadas) -- ruc tiene constraint UNIQUE, ver
    empresas_service.actualizar_empresa_activa para el manejo del 409
    si ya existe otra empresa con el mismo RUC."""

    region: str | None = Field(default=None, max_length=100)
    actividad_economica: str | None = Field(default=None, max_length=150)
    tamano_empresa: str | None = Field(default=None, max_length=50)
    ruc: str | None = Field(default=None, min_length=1, max_length=30)
    dv: str | None = Field(default=None, max_length=5)
    direccion: str | None = Field(default=None, max_length=500)
    telefono: str | None = Field(default=None, max_length=30)


class EmpresaCreateRequest(BaseModel):
    """Solo los datos mínimos de la empresa -- crear un usuario admin
    para ella es un paso aparte (pantalla "Agregar usuario", que un
    superadmin ya puede usar en cuanto entra a la empresa recién
    creada). Ver CLAUDE.md sección de superadmin."""

    razon_social: str = Field(min_length=1, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=200)
    ruc: str = Field(min_length=1, max_length=30)
    dv: str | None = Field(default=None, max_length=5)

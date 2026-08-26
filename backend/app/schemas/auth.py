import uuid

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class CambiarPasswordTemporalRequest(BaseModel):
    password_actual: str
    # Auditoría de seguridad 2026-08-25 (hallazgo B1): 8 agravaba C2
    # (fuerza bruta) al ser el mínimo típico de diccionario. No es
    # explotable por sí solo, pero subir el piso es gratis.
    password_nueva: str = Field(min_length=10)


class SeleccionarEmpresaRequest(BaseModel):
    empresa_id: uuid.UUID


class EmpresaAccesoOut(BaseModel):
    empresa_id: uuid.UUID
    razon_social: str
    nombre_comercial: str | None
    rol: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre_completo: str
    es_superadmin: bool
    puede_crear_empresas: bool
    debe_cambiar_password: bool


class MeOut(BaseModel):
    usuario: UsuarioOut
    empresa_activa_id: uuid.UUID | None
    rol_activo: str | None

import uuid

from pydantic import BaseModel, ConfigDict


class UsuarioAdminOut(BaseModel):
    """Fila de GET /usuarios (superadmin-only) -- solo usuarios con rol
    admin en al menos una empresa, ver usuarios_repo.listar_admins_globales."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre_completo: str
    es_superadmin: bool
    puede_crear_empresas: bool


class UsuarioPermisoUpdate(BaseModel):
    puede_crear_empresas: bool

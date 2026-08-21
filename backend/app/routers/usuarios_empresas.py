import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_roles
from app.models import Usuario
from app.schemas.usuarios import PasswordResetOut
from app.schemas.usuarios_empresas import UsuarioEmpresaCreate, UsuarioEmpresaOut, UsuarioEmpresaUpdate
from app.services import usuarios_empresas_service

router = APIRouter(prefix="/empresas/actual/usuarios", tags=["usuarios-empresa"])


@router.get("", response_model=list[UsuarioEmpresaOut])
def listar_usuarios(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> list[UsuarioEmpresaOut]:
    return usuarios_empresas_service.listar(db, empresa_id)


@router.post("", response_model=UsuarioEmpresaOut, status_code=201)
def agregar_usuario(
    body: UsuarioEmpresaCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> UsuarioEmpresaOut:
    return usuarios_empresas_service.agregar_usuario(db, empresa_id, usuario.id, body)


@router.patch("/{usuario_empresa_id}", response_model=UsuarioEmpresaOut)
def actualizar_acceso(
    usuario_empresa_id: uuid.UUID,
    body: UsuarioEmpresaUpdate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> UsuarioEmpresaOut:
    return usuarios_empresas_service.actualizar_acceso(
        db, empresa_id, usuario_empresa_id, usuario.id, body
    )


@router.post("/{usuario_empresa_id}/resetear-password", response_model=PasswordResetOut)
def resetear_password(
    usuario_empresa_id: uuid.UUID,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> PasswordResetOut:
    password_temporal, expira_en = usuarios_empresas_service.resetear_password(
        db, empresa_id, usuario_empresa_id, usuario.id
    )
    return PasswordResetOut(password_temporal=password_temporal, expira_en=expira_en)

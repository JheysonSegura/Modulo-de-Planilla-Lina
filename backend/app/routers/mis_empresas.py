import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_db_rls_empresa, require_admin_de_empresa, require_puede_crear_empresas
from app.models import Empresa, Usuario
from app.schemas.empresas import EmpresaOut
from app.schemas.usuarios import PasswordResetOut
from app.schemas.usuarios_empresas import UsuarioEmpresaCreate, UsuarioEmpresaOut, UsuarioEmpresaUpdate
from app.services import empresas_service, usuarios_empresas_service

router = APIRouter(prefix="/mis-empresas", tags=["mis-empresas"])


@router.get("", response_model=list[EmpresaOut])
def listar_mis_empresas(
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[Usuario, Depends(require_puede_crear_empresas)],
) -> list[Empresa]:
    return empresas_service.listar_mis_empresas_admin(db, usuario)


@router.get("/{empresa_id}/usuarios", response_model=list[UsuarioEmpresaOut])
def listar_usuarios(
    empresa_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls_empresa)],
    _usuario: Annotated[Usuario, Depends(require_admin_de_empresa)],
) -> list[UsuarioEmpresaOut]:
    return usuarios_empresas_service.listar(db, empresa_id)


@router.post("/{empresa_id}/usuarios", response_model=UsuarioEmpresaOut, status_code=status.HTTP_201_CREATED)
def agregar_usuario(
    empresa_id: uuid.UUID,
    body: UsuarioEmpresaCreate,
    db: Annotated[Session, Depends(get_db_rls_empresa)],
    usuario: Annotated[Usuario, Depends(require_admin_de_empresa)],
) -> UsuarioEmpresaOut:
    return usuarios_empresas_service.agregar_usuario(db, empresa_id, usuario.id, body)


@router.patch("/{empresa_id}/usuarios/{usuario_empresa_id}", response_model=UsuarioEmpresaOut)
def actualizar_acceso(
    empresa_id: uuid.UUID,
    usuario_empresa_id: uuid.UUID,
    body: UsuarioEmpresaUpdate,
    db: Annotated[Session, Depends(get_db_rls_empresa)],
    usuario: Annotated[Usuario, Depends(require_admin_de_empresa)],
) -> UsuarioEmpresaOut:
    return usuarios_empresas_service.actualizar_acceso(
        db, empresa_id, usuario_empresa_id, usuario.id, body
    )


@router.post("/{empresa_id}/usuarios/{usuario_empresa_id}/resetear-password", response_model=PasswordResetOut)
def resetear_password(
    empresa_id: uuid.UUID,
    usuario_empresa_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls_empresa)],
    usuario: Annotated[Usuario, Depends(require_admin_de_empresa)],
) -> PasswordResetOut:
    password_temporal, expira_en = usuarios_empresas_service.resetear_password(
        db, empresa_id, usuario_empresa_id, usuario.id
    )
    return PasswordResetOut(password_temporal=password_temporal, expira_en=expira_en)

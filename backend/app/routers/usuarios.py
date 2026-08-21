import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_superadmin
from app.models import Usuario
from app.schemas.usuarios import PasswordResetOut, UsuarioAdminOut, UsuarioPermisoUpdate
from app.services import usuarios_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioAdminOut])
def listar_admins(
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(require_superadmin)],
) -> list[UsuarioAdminOut]:
    return usuarios_service.listar_admins(db)


@router.patch("/{usuario_id}", response_model=UsuarioAdminOut)
def actualizar_permiso(
    usuario_id: uuid.UUID,
    body: UsuarioPermisoUpdate,
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(require_superadmin)],
) -> UsuarioAdminOut:
    return usuarios_service.actualizar_permiso_crear_empresas(db, usuario_id, body.puede_crear_empresas)


@router.post("/{usuario_id}/resetear-password", response_model=PasswordResetOut)
def resetear_password(
    usuario_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[Usuario, Depends(require_superadmin)],
) -> PasswordResetOut:
    password_temporal, expira_en = usuarios_service.resetear_password_superadmin(
        db, usuario_id, usuario.id
    )
    return PasswordResetOut(password_temporal=password_temporal, expira_en=expira_en)

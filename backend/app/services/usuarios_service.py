import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import usuarios as usuarios_repo
from app.schemas.usuarios import UsuarioAdminOut


def _a_out(usuario) -> UsuarioAdminOut:
    return UsuarioAdminOut.model_validate(usuario)


def listar_admins(db: Session) -> list[UsuarioAdminOut]:
    return [_a_out(u) for u in usuarios_repo.listar_admins_globales(db)]


def actualizar_permiso_crear_empresas(
    db: Session, usuario_id: uuid.UUID, valor: bool
) -> UsuarioAdminOut:
    usuario = usuarios_repo.get_by_id(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    usuario.puede_crear_empresas = valor
    db.commit()
    return _a_out(usuario)

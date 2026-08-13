import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Rol, Usuario, UsuarioEmpresa


def get_by_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == email))


def get_by_id(db: Session, usuario_id: uuid.UUID) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def crear(db: Session, usuario: Usuario) -> Usuario:
    db.add(usuario)
    db.flush()
    return usuario


def listar_admins_globales(db: Session) -> list[Usuario]:
    """Usuarios con rol 'admin' activo en al menos una empresa --
    candidatos a recibir el permiso puede_crear_empresas (ver
    require_puede_crear_empresas). Un usuario admin en varias empresas
    aparece una sola vez."""
    stmt = (
        select(Usuario)
        .join(UsuarioEmpresa, UsuarioEmpresa.usuario_id == Usuario.id)
        .join(Rol, Rol.id == UsuarioEmpresa.rol_id)
        .where(Rol.nombre == "admin", UsuarioEmpresa.activo.is_(True))
        .distinct()
        .order_by(Usuario.email)
    )
    return list(db.scalars(stmt).all())

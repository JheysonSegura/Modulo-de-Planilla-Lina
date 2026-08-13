import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Empresa, Rol, UsuarioEmpresa


def get(db: Session, empresa_id: uuid.UUID) -> Empresa | None:
    return db.get(Empresa, empresa_id)


def crear(db: Session, empresa: Empresa) -> Empresa:
    db.add(empresa)
    db.flush()
    return empresa


def listar_todas_activas(db: Session) -> list[Empresa]:
    """Solo para superadmin (ver auth_service.listar_empresas) -- a
    diferencia de listar_empresas_de_usuario, no filtra por membresía."""
    stmt = select(Empresa).where(Empresa.activo.is_(True)).order_by(Empresa.razon_social)
    return list(db.scalars(stmt).all())


def get_membresia_activa(
    db: Session, usuario_id: uuid.UUID, empresa_id: uuid.UUID
) -> UsuarioEmpresa | None:
    return db.scalar(
        select(UsuarioEmpresa).where(
            UsuarioEmpresa.usuario_id == usuario_id,
            UsuarioEmpresa.empresa_id == empresa_id,
            UsuarioEmpresa.activo.is_(True),
        )
    )


def get_rol(db: Session, rol_id: int) -> Rol | None:
    return db.get(Rol, rol_id)


def listar_empresas_de_usuario(
    db: Session, usuario_id: uuid.UUID
) -> list[tuple[UsuarioEmpresa, Empresa, Rol]]:
    stmt = (
        select(UsuarioEmpresa, Empresa, Rol)
        .join(Empresa, Empresa.id == UsuarioEmpresa.empresa_id)
        .join(Rol, Rol.id == UsuarioEmpresa.rol_id)
        .where(
            UsuarioEmpresa.usuario_id == usuario_id,
            UsuarioEmpresa.activo.is_(True),
            Empresa.activo.is_(True),
        )
        .order_by(Empresa.razon_social)
    )
    return list(db.execute(stmt).all())

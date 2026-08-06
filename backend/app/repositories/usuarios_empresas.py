import uuid

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.models import Rol, Usuario, UsuarioEmpresa

_COLUMNAS_OUT = (
    UsuarioEmpresa.id,
    UsuarioEmpresa.usuario_id,
    Usuario.email,
    Usuario.nombre_completo,
    Rol.nombre.label("rol"),
    UsuarioEmpresa.activo,
    UsuarioEmpresa.created_at,
)


def _query_base():
    return select(*_COLUMNAS_OUT).join(Usuario, UsuarioEmpresa.usuario_id == Usuario.id).join(
        Rol, UsuarioEmpresa.rol_id == Rol.id
    )


def listar_de_empresa(db: Session, empresa_id: uuid.UUID) -> list[Row]:
    stmt = _query_base().where(UsuarioEmpresa.empresa_id == empresa_id).order_by(Usuario.email)
    return list(db.execute(stmt).all())


def get_out(db: Session, usuario_empresa_id: uuid.UUID) -> Row | None:
    stmt = _query_base().where(UsuarioEmpresa.id == usuario_empresa_id)
    return db.execute(stmt).first()


def get(db: Session, usuario_empresa_id: uuid.UUID) -> UsuarioEmpresa | None:
    return db.get(UsuarioEmpresa, usuario_empresa_id)


def get_por_usuario_y_empresa(
    db: Session, usuario_id: uuid.UUID, empresa_id: uuid.UUID
) -> UsuarioEmpresa | None:
    stmt = select(UsuarioEmpresa).where(
        UsuarioEmpresa.usuario_id == usuario_id, UsuarioEmpresa.empresa_id == empresa_id
    )
    return db.scalar(stmt)


def get_rol_por_nombre(db: Session, nombre: str) -> Rol | None:
    return db.scalar(select(Rol).where(Rol.nombre == nombre))


def crear(db: Session, vinculo: UsuarioEmpresa) -> UsuarioEmpresa:
    db.add(vinculo)
    db.flush()
    return vinculo


def actualizar(db: Session, vinculo: UsuarioEmpresa, rol_id: int | None, activo: bool | None) -> UsuarioEmpresa:
    if rol_id is not None:
        vinculo.rol_id = rol_id
    if activo is not None:
        vinculo.activo = activo
    db.flush()
    return vinculo

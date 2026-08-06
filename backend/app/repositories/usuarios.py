import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Usuario


def get_by_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.email == email))


def get_by_id(db: Session, usuario_id: uuid.UUID) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def crear(db: Session, usuario: Usuario) -> Usuario:
    db.add(usuario)
    db.flush()
    return usuario

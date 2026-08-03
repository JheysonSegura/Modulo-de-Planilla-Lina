import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contrato


def crear(db: Session, contrato: Contrato) -> Contrato:
    db.add(contrato)
    db.flush()
    return contrato


def get(db: Session, contrato_id: uuid.UUID) -> Contrato | None:
    return db.get(Contrato, contrato_id)


def listar_de_empleado(db: Session, empleado_id: uuid.UUID) -> list[Contrato]:
    stmt = (
        select(Contrato)
        .where(Contrato.empleado_id == empleado_id)
        .order_by(Contrato.fecha_inicio.desc())
    )
    return list(db.execute(stmt).scalars().all())

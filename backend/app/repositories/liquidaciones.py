import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Liquidacion


def crear(db: Session, liquidacion: Liquidacion) -> Liquidacion:
    db.add(liquidacion)
    db.flush()
    return liquidacion


def get(db: Session, liquidacion_id: uuid.UUID) -> Liquidacion | None:
    return db.get(Liquidacion, liquidacion_id)


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[Liquidacion]:
    stmt = (
        select(Liquidacion)
        .where(Liquidacion.contrato_id == contrato_id)
        .order_by(Liquidacion.fecha_terminacion)
    )
    return list(db.execute(stmt).scalars().all())

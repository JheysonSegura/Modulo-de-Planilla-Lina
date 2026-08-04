import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MovimientoPlanilla


def crear(db: Session, movimiento: MovimientoPlanilla) -> MovimientoPlanilla:
    db.add(movimiento)
    db.flush()
    return movimiento


def listar_de_planilla(db: Session, planilla_id: uuid.UUID) -> list[MovimientoPlanilla]:
    stmt = select(MovimientoPlanilla).where(MovimientoPlanilla.planilla_id == planilla_id)
    return list(db.execute(stmt).scalars().all())

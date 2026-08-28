import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HistorialCargo


def crear(db: Session, historial: HistorialCargo) -> HistorialCargo:
    db.add(historial)
    db.flush()
    return historial


def get_abierto(db: Session, contrato_id: uuid.UUID) -> HistorialCargo | None:
    """El registro vigente "actual": el que todavía no tiene
    fecha_vigencia_hasta. Debe haber como máximo uno por contrato."""
    stmt = select(HistorialCargo).where(
        HistorialCargo.contrato_id == contrato_id,
        HistorialCargo.fecha_vigencia_hasta.is_(None),
    )
    return db.scalar(stmt)


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[HistorialCargo]:
    stmt = (
        select(HistorialCargo)
        .where(HistorialCargo.contrato_id == contrato_id)
        .order_by(HistorialCargo.fecha_vigencia_desde)
    )
    return list(db.execute(stmt).scalars().all())

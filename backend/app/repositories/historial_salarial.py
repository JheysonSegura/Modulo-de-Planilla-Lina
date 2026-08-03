import datetime
import uuid

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import HistorialSalarial


def crear(db: Session, historial: HistorialSalarial) -> HistorialSalarial:
    db.add(historial)
    db.flush()
    return historial


def get_abierto(db: Session, contrato_id: uuid.UUID) -> HistorialSalarial | None:
    """El registro vigente "actual": el que todavía no tiene
    fecha_vigencia_hasta. Debe haber como máximo uno por contrato."""
    stmt = select(HistorialSalarial).where(
        HistorialSalarial.contrato_id == contrato_id,
        HistorialSalarial.fecha_vigencia_hasta.is_(None),
    )
    return db.scalar(stmt)


def get_vigente_en_fecha(
    db: Session, contrato_id: uuid.UUID, fecha: datetime.date
) -> HistorialSalarial | None:
    stmt = select(HistorialSalarial).where(
        HistorialSalarial.contrato_id == contrato_id,
        HistorialSalarial.fecha_vigencia_desde <= fecha,
        or_(
            HistorialSalarial.fecha_vigencia_hasta.is_(None),
            HistorialSalarial.fecha_vigencia_hasta >= fecha,
        ),
    )
    return db.scalar(stmt)


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[HistorialSalarial]:
    stmt = (
        select(HistorialSalarial)
        .where(HistorialSalarial.contrato_id == contrato_id)
        .order_by(HistorialSalarial.fecha_vigencia_desde)
    )
    return list(db.execute(stmt).scalars().all())

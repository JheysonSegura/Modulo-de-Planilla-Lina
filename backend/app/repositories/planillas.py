import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Planilla


def crear(db: Session, planilla: Planilla) -> Planilla:
    db.add(planilla)
    db.flush()
    return planilla


def get(db: Session, planilla_id: uuid.UUID) -> Planilla | None:
    return db.get(Planilla, planilla_id)


def buscar_por_periodo(
    db: Session,
    empresa_id: uuid.UUID,
    tipo: str,
    periodo_inicio: datetime.date,
    periodo_fin: datetime.date,
    excluir_estado: str = "anulada",
) -> Planilla | None:
    stmt = select(Planilla).where(
        Planilla.empresa_id == empresa_id,
        Planilla.tipo == tipo,
        Planilla.periodo_inicio == periodo_inicio,
        Planilla.periodo_fin == periodo_fin,
        Planilla.estado != excluir_estado,
    )
    return db.scalar(stmt)

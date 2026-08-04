import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConceptoVariablePendiente


def crear(db: Session, concepto: ConceptoVariablePendiente) -> ConceptoVariablePendiente:
    db.add(concepto)
    db.flush()
    return concepto


def get(db: Session, concepto_id: uuid.UUID) -> ConceptoVariablePendiente | None:
    return db.get(ConceptoVariablePendiente, concepto_id)


def listar_de_contrato(
    db: Session,
    contrato_id: uuid.UUID,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
) -> list[ConceptoVariablePendiente]:
    stmt = select(ConceptoVariablePendiente).where(
        ConceptoVariablePendiente.contrato_id == contrato_id
    )
    if desde is not None:
        stmt = stmt.where(ConceptoVariablePendiente.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(ConceptoVariablePendiente.fecha <= hasta)
    stmt = stmt.order_by(ConceptoVariablePendiente.fecha, ConceptoVariablePendiente.created_at)
    return list(db.execute(stmt).scalars().all())


def listar_pendientes_de_contrato(
    db: Session,
    contrato_id: uuid.UUID,
    desde: datetime.date,
    hasta: datetime.date,
) -> list[ConceptoVariablePendiente]:
    """Solo los no aplicados todavía a ninguna planilla, dentro del
    rango del período que está generando el motor de planilla."""
    stmt = (
        select(ConceptoVariablePendiente)
        .where(
            ConceptoVariablePendiente.contrato_id == contrato_id,
            ConceptoVariablePendiente.fecha >= desde,
            ConceptoVariablePendiente.fecha <= hasta,
            ConceptoVariablePendiente.aplicado.is_(False),
        )
        .order_by(ConceptoVariablePendiente.fecha, ConceptoVariablePendiente.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def eliminar(db: Session, concepto: ConceptoVariablePendiente) -> None:
    db.delete(concepto)
    db.flush()

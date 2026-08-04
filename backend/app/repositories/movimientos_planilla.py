import decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MovimientoPlanilla, Planilla


def crear(db: Session, movimiento: MovimientoPlanilla) -> MovimientoPlanilla:
    db.add(movimiento)
    db.flush()
    return movimiento


def listar_de_planilla(db: Session, planilla_id: uuid.UUID) -> list[MovimientoPlanilla]:
    stmt = select(MovimientoPlanilla).where(MovimientoPlanilla.planilla_id == planilla_id)
    return list(db.execute(stmt).scalars().all())


def sumar_isr_retenido_del_anio(
    db: Session,
    contrato_id: uuid.UUID,
    anio: int,
    excluir_planilla_id: uuid.UUID | None = None,
) -> decimal.Decimal:
    """ISR ya retenido este año calendario para este contrato, en
    planillas no anuladas -- usado para el ajuste progresivo del ISR
    (Fase 7): cada período reconcilia contra lo realmente retenido
    antes, no vuelve a repartir el impuesto anual desde cero."""
    stmt = (
        select(func.coalesce(func.sum(MovimientoPlanilla.isr_retenido), 0))
        .join(Planilla, Planilla.id == MovimientoPlanilla.planilla_id)
        .where(
            MovimientoPlanilla.contrato_id == contrato_id,
            func.extract("year", Planilla.periodo_inicio) == anio,
            Planilla.estado != "anulada",
        )
    )
    if excluir_planilla_id is not None:
        stmt = stmt.where(Planilla.id != excluir_planilla_id)
    return decimal.Decimal(db.scalar(stmt))

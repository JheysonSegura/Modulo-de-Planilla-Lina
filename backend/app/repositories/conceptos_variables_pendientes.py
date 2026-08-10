import datetime
import decimal
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import ConceptoVariablePendiente, MovimientoPlanilla


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


def revertir_aplicados_de_planilla(db: Session, planilla_id: uuid.UUID) -> None:
    """Al anular una planilla (planilla_service.anular_planilla): libera
    los conceptos variables pendientes que esa planilla había marcado
    como aplicados, para que la planilla de reemplazo del mismo período
    los vuelva a recoger (listar_pendientes_de_contrato solo trae los
    no aplicados)."""
    subquery = select(MovimientoPlanilla.id).where(MovimientoPlanilla.planilla_id == planilla_id)
    stmt = (
        update(ConceptoVariablePendiente)
        .where(ConceptoVariablePendiente.movimiento_planilla_id.in_(subquery))
        .values(aplicado=False, movimiento_planilla_id=None)
    )
    db.execute(stmt)


def sumar_monto_ingresos_periodo(
    db: Session, contrato_id: uuid.UUID, desde: datetime.date, hasta: datetime.date
) -> decimal.Decimal:
    """Suma de conceptos tipo 'ingreso' (comisiones, bonos, etc.)
    devengados por el contrato en [desde, hasta], aplicados o no --
    usado por decimo_service para la base de "ingresos brutos
    devengados" (Fase de corrección del décimo, 2026-08-06). Se usa
    esta tabla (no `conceptos_variables`, la de lo ya aplicado a un
    movimiento) porque es la única con fecha propia por día; sumar de
    las dos duplicaría lo ya aplicado."""
    stmt = select(func.coalesce(func.sum(ConceptoVariablePendiente.monto), 0)).where(
        ConceptoVariablePendiente.contrato_id == contrato_id,
        ConceptoVariablePendiente.tipo == "ingreso",
        ConceptoVariablePendiente.fecha >= desde,
        ConceptoVariablePendiente.fecha <= hasta,
    )
    return decimal.Decimal(db.scalar(stmt))

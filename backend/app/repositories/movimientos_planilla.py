import datetime
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


def sumar_salario_bruto_periodo(
    db: Session,
    contrato_id: uuid.UUID,
    fecha_desde_exclusive: datetime.date,
    fecha_hasta_inclusive: datetime.date,
) -> decimal.Decimal:
    """Suma salario_bruto (fijo + horas extra + variables de ingreso,
    ver planilla_service._calcular... ) de los movimientos cuyo
    periodo_fin cae en (fecha_desde_exclusive, fecha_hasta_inclusive],
    en planillas no anuladas. Usado para el salario promedio del
    Art. 149/226 CT (liquidaciones, Fase 10) -- a diferencia de
    sumar_isr_retenido_del_anio, aquí se filtra por periodo_fin (no por
    año calendario) porque las ventanas de 6 meses/30 días/5 años no
    respetan límites de año."""
    stmt = (
        select(func.coalesce(func.sum(MovimientoPlanilla.salario_bruto), 0))
        .join(Planilla, Planilla.id == MovimientoPlanilla.planilla_id)
        .where(
            MovimientoPlanilla.contrato_id == contrato_id,
            Planilla.estado != "anulada",
            Planilla.periodo_fin > fecha_desde_exclusive,
            Planilla.periodo_fin <= fecha_hasta_inclusive,
        )
    )
    return decimal.Decimal(db.scalar(stmt))


def obtener_fecha_minima_periodo(
    db: Session,
    contrato_id: uuid.UUID,
    fecha_desde_exclusive: datetime.date,
    fecha_hasta_inclusive: datetime.date,
) -> datetime.date | None:
    """periodo_inicio más antiguo entre los movimientos que caen en la
    ventana -- usado para promediar solo sobre el tramo con datos
    reales, en vez de diluir el promedio con años de antigüedad que no
    tienen planillas cargadas en este sistema (Fase 10, Art. 226 CT)."""
    stmt = select(func.min(Planilla.periodo_inicio)).join(
        MovimientoPlanilla, MovimientoPlanilla.planilla_id == Planilla.id
    ).where(
        MovimientoPlanilla.contrato_id == contrato_id,
        Planilla.estado != "anulada",
        Planilla.periodo_fin > fecha_desde_exclusive,
        Planilla.periodo_fin <= fecha_hasta_inclusive,
    )
    return db.scalar(stmt)


def obtener_ultimo_periodo_fin_pagado(
    db: Session, contrato_id: uuid.UUID
) -> datetime.date | None:
    """Fecha de corte de la última planilla REGULAR (mensual/quincenal,
    no décimo) no anulada de este contrato -- usado para saber desde
    cuándo hay salario pendiente de pagar al liquidar (Fase 10)."""
    stmt = (
        select(func.max(Planilla.periodo_fin))
        .join(MovimientoPlanilla, MovimientoPlanilla.planilla_id == Planilla.id)
        .where(
            MovimientoPlanilla.contrato_id == contrato_id,
            Planilla.estado != "anulada",
            Planilla.tipo.in_(("mensual", "quincenal")),
        )
    )
    return db.scalar(stmt)

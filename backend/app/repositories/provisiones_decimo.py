import datetime
import decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProvisionDecimo


def get(db: Session, provision_id: uuid.UUID) -> ProvisionDecimo | None:
    return db.get(ProvisionDecimo, provision_id)


def get_provision(
    db: Session, contrato_id: uuid.UUID, cuatrimestre: str, anio: int
) -> ProvisionDecimo | None:
    stmt = select(ProvisionDecimo).where(
        ProvisionDecimo.contrato_id == contrato_id,
        ProvisionDecimo.cuatrimestre == cuatrimestre,
        ProvisionDecimo.anio == anio,
    )
    return db.scalar(stmt)


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[ProvisionDecimo]:
    stmt = (
        select(ProvisionDecimo)
        .where(ProvisionDecimo.contrato_id == contrato_id)
        .order_by(ProvisionDecimo.anio, ProvisionDecimo.fecha_pago_programada)
    )
    return list(db.execute(stmt).scalars().all())


def upsert_provision(
    db: Session,
    empresa_id: uuid.UUID,
    contrato_id: uuid.UUID,
    cuatrimestre: str,
    anio: int,
    monto_acumulado: decimal.Decimal,
    fecha_pago_programada: datetime.date,
) -> ProvisionDecimo:
    """Recalcula completo cada vez (igual que _recalcular_semana en
    Fase 5): una planilla generada fuera de orden no descuadra la
    provisión, porque siempre se vuelve a sumar desde cero."""
    provision = get_provision(db, contrato_id, cuatrimestre, anio)
    if provision is None:
        provision = ProvisionDecimo(
            empresa_id=empresa_id,
            contrato_id=contrato_id,
            cuatrimestre=cuatrimestre,
            anio=anio,
            monto_acumulado=monto_acumulado,
            fecha_pago_programada=fecha_pago_programada,
        )
        db.add(provision)
    else:
        provision.monto_acumulado = monto_acumulado
    db.flush()
    return provision


def marcar_pagada(
    db: Session,
    provision: ProvisionDecimo,
    movimiento_planilla_id: uuid.UUID,
    fecha_pago_real: datetime.date,
) -> ProvisionDecimo:
    provision.pagado = True
    provision.movimiento_planilla_id = movimiento_planilla_id
    provision.fecha_pago_real = fecha_pago_real
    db.flush()
    return provision

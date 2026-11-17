import datetime
import decimal
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Contrato,
    CuotaDescuento,
    DescuentoRecurrente,
    Liquidacion,
    MovimientoPlanilla,
    Planilla,
)


def crear(db: Session, descuento: DescuentoRecurrente) -> DescuentoRecurrente:
    db.add(descuento)
    db.flush()
    return descuento


def get(db: Session, descuento_id: uuid.UUID) -> DescuentoRecurrente | None:
    return db.get(DescuentoRecurrente, descuento_id)


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[DescuentoRecurrente]:
    stmt = (
        select(DescuentoRecurrente)
        .where(DescuentoRecurrente.contrato_id == contrato_id)
        .order_by(DescuentoRecurrente.fecha_inicio, DescuentoRecurrente.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def listar_activos_de_contrato(
    db: Session, contrato_id: uuid.UUID, hasta: datetime.date
) -> list[DescuentoRecurrente]:
    stmt = (
        select(DescuentoRecurrente)
        .where(
            DescuentoRecurrente.contrato_id == contrato_id,
            DescuentoRecurrente.estado == "activo",
            DescuentoRecurrente.fecha_inicio <= hasta,
        )
        .order_by(DescuentoRecurrente.fecha_inicio, DescuentoRecurrente.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def crear_cuota(db: Session, cuota: CuotaDescuento) -> CuotaDescuento:
    db.add(cuota)
    db.flush()
    return cuota


def _cuotas_vigentes():
    """Cuotas que siguen contando: las de una planilla o liquidación no
    anulada. Anular cualquiera de las dos devuelve la cuota al saldo sin
    tocar esta tabla."""
    return (
        select(CuotaDescuento)
        .outerjoin(MovimientoPlanilla, MovimientoPlanilla.id == CuotaDescuento.movimiento_planilla_id)
        .outerjoin(Planilla, Planilla.id == MovimientoPlanilla.planilla_id)
        .outerjoin(Liquidacion, Liquidacion.id == CuotaDescuento.liquidacion_id)
        .where(
            or_(
                and_(CuotaDescuento.movimiento_planilla_id.is_not(None), Planilla.estado != "anulada"),
                and_(CuotaDescuento.liquidacion_id.is_not(None), Liquidacion.estado != "anulada"),
            )
        )
    )


def sumar_cobrado(db: Session, descuento_id: uuid.UUID) -> decimal.Decimal:
    sub = _cuotas_vigentes().where(CuotaDescuento.descuento_id == descuento_id).subquery()
    total = db.execute(select(func.coalesce(func.sum(sub.c.monto), 0))).scalar_one()
    return decimal.Decimal(total)


def contar_cobros(db: Session, descuento_id: uuid.UUID) -> int:
    sub = _cuotas_vigentes().where(CuotaDescuento.descuento_id == descuento_id).subquery()
    return db.execute(select(func.count()).select_from(sub)).scalar_one()


def existe_cobro_en_fecha(db: Session, descuento_id: uuid.UUID, fecha: datetime.date) -> bool:
    stmt = _cuotas_vigentes().where(
        CuotaDescuento.descuento_id == descuento_id, CuotaDescuento.fecha_cobro == fecha
    )
    return db.execute(stmt.limit(1)).first() is not None


def contar_cobros_antes_de(db: Session, descuento_id: uuid.UUID, fecha: datetime.date) -> int:
    sub = (
        _cuotas_vigentes()
        .where(CuotaDescuento.descuento_id == descuento_id, CuotaDescuento.fecha_cobro < fecha)
        .subquery()
    )
    return db.execute(select(func.count()).select_from(sub)).scalar_one()


def listar_cuotas_con_origen(
    db: Session, descuento_id: uuid.UUID
) -> list[tuple[CuotaDescuento, Planilla | None, Liquidacion | None]]:
    """Todas las cuotas del descuento (incluidas las de planillas o
    liquidaciones anuladas, para el historial), con su origen."""
    stmt = (
        select(CuotaDescuento, Planilla, Liquidacion)
        .outerjoin(MovimientoPlanilla, MovimientoPlanilla.id == CuotaDescuento.movimiento_planilla_id)
        .outerjoin(Planilla, Planilla.id == MovimientoPlanilla.planilla_id)
        .outerjoin(Liquidacion, Liquidacion.id == CuotaDescuento.liquidacion_id)
        .where(CuotaDescuento.descuento_id == descuento_id)
        .order_by(CuotaDescuento.fecha_cobro, CuotaDescuento.created_at)
    )
    return [tuple(fila) for fila in db.execute(stmt).all()]


def tiene_cuotas(db: Session, descuento_id: uuid.UUID) -> bool:
    stmt = select(CuotaDescuento.id).where(CuotaDescuento.descuento_id == descuento_id).limit(1)
    return db.execute(stmt).first() is not None


def listar_cuotas_de_planilla(
    db: Session, planilla_id: uuid.UUID
) -> list[tuple[CuotaDescuento, DescuentoRecurrente, Contrato]]:
    stmt = (
        select(CuotaDescuento, DescuentoRecurrente, Contrato)
        .join(MovimientoPlanilla, MovimientoPlanilla.id == CuotaDescuento.movimiento_planilla_id)
        .join(DescuentoRecurrente, DescuentoRecurrente.id == CuotaDescuento.descuento_id)
        .join(Contrato, Contrato.id == DescuentoRecurrente.contrato_id)
        .where(MovimientoPlanilla.planilla_id == planilla_id)
        .order_by(DescuentoRecurrente.acreedor, DescuentoRecurrente.referencia, CuotaDescuento.fecha_cobro)
    )
    return [tuple(fila) for fila in db.execute(stmt).all()]

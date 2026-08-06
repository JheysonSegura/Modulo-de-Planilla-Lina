import datetime
import decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RegistroHorasExtra


def crear(db: Session, registro: RegistroHorasExtra) -> RegistroHorasExtra:
    db.add(registro)
    db.flush()
    return registro


def get(db: Session, registro_id: uuid.UUID) -> RegistroHorasExtra | None:
    return db.get(RegistroHorasExtra, registro_id)


def listar_de_contrato(
    db: Session,
    contrato_id: uuid.UUID,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
) -> list[RegistroHorasExtra]:
    stmt = select(RegistroHorasExtra).where(RegistroHorasExtra.contrato_id == contrato_id)
    if desde is not None:
        stmt = stmt.where(RegistroHorasExtra.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(RegistroHorasExtra.fecha <= hasta)
    stmt = stmt.order_by(RegistroHorasExtra.fecha, RegistroHorasExtra.created_at)
    return list(db.execute(stmt).scalars().all())


def listar_de_semana_iso(
    db: Session, contrato_id: uuid.UUID, fecha: datetime.date
) -> list[RegistroHorasExtra]:
    """Semana ISO (lunes-domingo) que contiene `fecha`, para recalcular
    el tope de 9h/semana del Art. 36 CT."""
    lunes = fecha - datetime.timedelta(days=fecha.isoweekday() - 1)
    domingo = lunes + datetime.timedelta(days=6)
    return listar_de_contrato(db, contrato_id, desde=lunes, hasta=domingo)


def eliminar(db: Session, registro: RegistroHorasExtra) -> None:
    db.delete(registro)
    db.flush()


def sumar_monto_periodo(
    db: Session, contrato_id: uuid.UUID, desde: datetime.date, hasta: datetime.date
) -> decimal.Decimal:
    """Suma de monto_calculado devengado por el contrato en [desde,
    hasta] -- usado por decimo_service para la base de "ingresos
    brutos devengados" (Fase de corrección del décimo, 2026-08-06)."""
    stmt = select(func.coalesce(func.sum(RegistroHorasExtra.monto_calculado), 0)).where(
        RegistroHorasExtra.contrato_id == contrato_id,
        RegistroHorasExtra.fecha >= desde,
        RegistroHorasExtra.fecha <= hasta,
    )
    return decimal.Decimal(db.scalar(stmt))

import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ParametroIsr


def obtener_vigente(db: Session, fecha: datetime.date) -> ParametroIsr | None:
    """Devuelve None si no hay ningún parámetro sembrado para esa
    fecha -- estado normal mientras el tratamiento del décimo en el
    ISR no está confirmado por el contador (ver migración
    0014_parametros_isr)."""
    stmt = select(ParametroIsr).where(
        ParametroIsr.fecha_inicio <= fecha,
        or_(ParametroIsr.fecha_fin.is_(None), ParametroIsr.fecha_fin >= fecha),
    )
    return db.scalar(stmt)

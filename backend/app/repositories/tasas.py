import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import TasaVigente


def obtener_tasa_vigente(
    db: Session, tipo_tasa: str, fecha: datetime.date
) -> TasaVigente | None:
    stmt = select(TasaVigente).where(
        TasaVigente.tipo_tasa == tipo_tasa,
        TasaVigente.fecha_inicio <= fecha,
        or_(TasaVigente.fecha_fin.is_(None), TasaVigente.fecha_fin >= fecha),
    )
    return db.scalar(stmt)

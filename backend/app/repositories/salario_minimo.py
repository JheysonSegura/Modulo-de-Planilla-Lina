import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import SalarioMinimoVigente


def listar_vigente_en_fecha(db: Session, fecha: datetime.date) -> list[SalarioMinimoVigente]:
    stmt = select(SalarioMinimoVigente).where(
        SalarioMinimoVigente.fecha_inicio <= fecha,
        or_(
            SalarioMinimoVigente.fecha_fin.is_(None),
            SalarioMinimoVigente.fecha_fin >= fecha,
        ),
    )
    return list(db.execute(stmt).scalars().all())

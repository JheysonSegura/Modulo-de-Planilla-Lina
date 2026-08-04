import datetime
import decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import TramoIsr


def obtener_tramo_aplicable(
    db: Session, renta_neta_anual: decimal.Decimal, fecha: datetime.date
) -> TramoIsr | None:
    """Primer tramo (ordenado por monto_desde ascendente) donde
    monto_hasta es NULL o la renta cabe dentro de él. $11,000 exactos
    caen en el tramo exento (monto_hasta=11000), no en el de 15%,
    coherente con "exento HASTA $11,000" (CLAUDE.md sección 4)."""
    stmt = (
        select(TramoIsr)
        .where(
            TramoIsr.fecha_inicio <= fecha,
            or_(TramoIsr.fecha_fin.is_(None), TramoIsr.fecha_fin >= fecha),
        )
        .order_by(TramoIsr.monto_desde)
    )
    tramos = list(db.execute(stmt).scalars().all())
    for tramo in tramos:
        if tramo.monto_hasta is None or renta_neta_anual <= tramo.monto_hasta:
            return tramo
    return None

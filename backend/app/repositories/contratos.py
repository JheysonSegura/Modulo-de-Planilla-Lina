import datetime
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Contrato


def crear(db: Session, contrato: Contrato) -> Contrato:
    db.add(contrato)
    db.flush()
    return contrato


def get(db: Session, contrato_id: uuid.UUID) -> Contrato | None:
    return db.get(Contrato, contrato_id)


def listar_de_empleado(db: Session, empleado_id: uuid.UUID) -> list[Contrato]:
    stmt = (
        select(Contrato)
        .where(Contrato.empleado_id == empleado_id)
        .order_by(Contrato.fecha_inicio.desc())
    )
    return list(db.execute(stmt).scalars().all())


def listar_vigentes_en_periodo(
    db: Session,
    empresa_id: uuid.UUID,
    periodo_inicio: datetime.date,
    periodo_fin: datetime.date,
) -> list[Contrato]:
    """Contratos cuyos días trabajados se solapan con [periodo_inicio,
    periodo_fin], sin filtrar por estado: un contrato recién terminado
    dentro del período igual trabajó esos días y debe cobrarlos (la
    liquidación final es una fase aparte, no se resuelve aquí)."""
    stmt = (
        select(Contrato)
        .where(
            Contrato.empresa_id == empresa_id,
            Contrato.fecha_inicio <= periodo_fin,
            or_(
                Contrato.fecha_fin_real.is_(None),
                Contrato.fecha_fin_real >= periodo_inicio,
            ),
        )
        .order_by(Contrato.fecha_inicio)
    )
    return list(db.execute(stmt).scalars().all())

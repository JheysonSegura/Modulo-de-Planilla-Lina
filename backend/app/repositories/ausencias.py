import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ausencia


def crear(
    db: Session,
    empresa_id: uuid.UUID,
    contrato_id: uuid.UUID,
    tipo: str,
    fecha_desde: datetime.date,
    fecha_hasta: datetime.date,
    certificado_ref: str | None,
) -> Ausencia:
    ausencia = Ausencia(
        empresa_id=empresa_id,
        contrato_id=contrato_id,
        tipo=tipo,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        certificado_ref=certificado_ref,
    )
    db.add(ausencia)
    db.flush()
    return ausencia


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[Ausencia]:
    stmt = (
        select(Ausencia)
        .where(Ausencia.contrato_id == contrato_id)
        .order_by(Ausencia.fecha_desde)
    )
    return list(db.execute(stmt).scalars().all())


def obtener(db: Session, ausencia_id: uuid.UUID) -> Ausencia | None:
    return db.get(Ausencia, ausencia_id)

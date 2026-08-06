import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditoriaCambio


def crear(db: Session, registro: AuditoriaCambio) -> AuditoriaCambio:
    db.add(registro)
    db.flush()
    return registro


def listar(
    db: Session,
    empleado_id: uuid.UUID | None = None,
    tabla_afectada: str | None = None,
    accion: str | None = None,
) -> list[AuditoriaCambio]:
    stmt = select(AuditoriaCambio)
    if empleado_id is not None:
        stmt = stmt.where(AuditoriaCambio.empleado_id == empleado_id)
    if tabla_afectada is not None:
        stmt = stmt.where(AuditoriaCambio.tabla_afectada == tabla_afectada)
    if accion is not None:
        stmt = stmt.where(AuditoriaCambio.accion == accion)
    stmt = stmt.order_by(AuditoriaCambio.created_at.desc())
    return list(db.execute(stmt).scalars().all())

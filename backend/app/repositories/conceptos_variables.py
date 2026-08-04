import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConceptoVariable


def crear(db: Session, concepto: ConceptoVariable) -> ConceptoVariable:
    db.add(concepto)
    db.flush()
    return concepto


def listar_de_movimiento(db: Session, movimiento_planilla_id: uuid.UUID) -> list[ConceptoVariable]:
    stmt = select(ConceptoVariable).where(
        ConceptoVariable.movimiento_planilla_id == movimiento_planilla_id
    )
    return list(db.execute(stmt).scalars().all())

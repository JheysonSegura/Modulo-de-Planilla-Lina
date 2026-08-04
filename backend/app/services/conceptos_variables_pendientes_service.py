import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ConceptoVariablePendiente, Contrato
from app.repositories import conceptos_variables_pendientes as pendientes_repo


def crear_pendiente(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    fecha: datetime.date,
    tipo: str,
    codigo: str,
    monto: decimal.Decimal,
    descripcion: str | None = None,
    usuario_id: uuid.UUID | None = None,
) -> ConceptoVariablePendiente:
    concepto = ConceptoVariablePendiente(
        empresa_id=empresa_id,
        contrato_id=contrato.id,
        fecha=fecha,
        tipo=tipo,
        codigo=codigo,
        descripcion=descripcion,
        monto=monto,
        registrado_por_usuario_id=usuario_id,
    )
    pendientes_repo.crear(db, concepto)
    db.commit()
    return concepto


def obtener(db: Session, concepto_id: uuid.UUID) -> ConceptoVariablePendiente:
    concepto = pendientes_repo.get(db, concepto_id)
    if concepto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concepto variable pendiente no encontrado")
    return concepto


def listar_de_contrato(
    db: Session,
    contrato_id: uuid.UUID,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
) -> list[ConceptoVariablePendiente]:
    return pendientes_repo.listar_de_contrato(db, contrato_id, desde, hasta)


def eliminar(db: Session, concepto: ConceptoVariablePendiente) -> None:
    if concepto.aplicado:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede eliminar un concepto variable que ya fue aplicado a una planilla.",
        )
    pendientes_repo.eliminar(db, concepto)
    db.commit()

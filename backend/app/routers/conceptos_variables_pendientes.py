import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_escritura
from app.models import ConceptoVariablePendiente, Usuario
from app.schemas.conceptos_variables_pendientes import (
    ConceptoVariablePendienteCreate,
    ConceptoVariablePendienteOut,
)
from app.services import conceptos_variables_pendientes_service, contratos_service

router = APIRouter(tags=["conceptos-variables-pendientes"])


@router.post(
    "/contratos/{contrato_id}/conceptos-variables-pendientes",
    response_model=ConceptoVariablePendienteOut,
    status_code=201,
)
def crear_concepto_variable_pendiente(
    contrato_id: uuid.UUID,
    body: ConceptoVariablePendienteCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> ConceptoVariablePendiente:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return conceptos_variables_pendientes_service.crear_pendiente(
        db,
        empresa_id,
        contrato,
        body.fecha,
        body.tipo,
        body.codigo,
        body.monto,
        descripcion=body.descripcion,
        usuario_id=usuario.id,
    )


@router.get(
    "/contratos/{contrato_id}/conceptos-variables-pendientes",
    response_model=list[ConceptoVariablePendienteOut],
)
def listar_conceptos_variables_pendientes(
    contrato_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    desde: Annotated[datetime.date | None, Query()] = None,
    hasta: Annotated[datetime.date | None, Query()] = None,
) -> list[ConceptoVariablePendiente]:
    contratos_service.obtener_contrato(db, contrato_id)
    return conceptos_variables_pendientes_service.listar_de_contrato(db, contrato_id, desde, hasta)


@router.delete(
    "/contratos/{contrato_id}/conceptos-variables-pendientes/{concepto_id}", status_code=204
)
def eliminar_concepto_variable_pendiente(
    contrato_id: uuid.UUID,
    concepto_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> None:
    concepto = conceptos_variables_pendientes_service.obtener(db, concepto_id)
    if concepto.contrato_id != contrato_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concepto no encontrado para este contrato")
    conceptos_variables_pendientes_service.eliminar(db, concepto)

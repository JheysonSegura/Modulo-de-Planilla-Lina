import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_escritura
from app.models import RegistroHorasExtra, Usuario
from app.schemas.horas_extra import RegistroHorasExtraCreate, RegistroHorasExtraOut
from app.services import contratos_service, horas_extra_service

router = APIRouter(tags=["horas-extra"])


@router.post(
    "/contratos/{contrato_id}/horas-extra",
    response_model=RegistroHorasExtraOut,
    status_code=201,
)
def registrar_hora_extra(
    contrato_id: uuid.UUID,
    body: RegistroHorasExtraCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> RegistroHorasExtra:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return horas_extra_service.registrar_hora_extra(
        db,
        empresa_id,
        contrato,
        body.fecha,
        body.tipo_hora,
        body.tipo_dia,
        body.horas,
        usuario_id=usuario.id,
        observaciones=body.observaciones,
    )


@router.get("/contratos/{contrato_id}/horas-extra", response_model=list[RegistroHorasExtraOut])
def listar_horas_extra(
    contrato_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    desde: Annotated[datetime.date | None, Query()] = None,
    hasta: Annotated[datetime.date | None, Query()] = None,
) -> list[RegistroHorasExtra]:
    contratos_service.obtener_contrato(db, contrato_id)
    return horas_extra_service.listar_de_contrato(db, contrato_id, desde, hasta)


@router.delete("/contratos/{contrato_id}/horas-extra/{registro_id}", status_code=204)
def eliminar_hora_extra(
    contrato_id: uuid.UUID,
    registro_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> None:
    registro = horas_extra_service.obtener_registro(db, registro_id)
    if registro.contrato_id != contrato_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro no encontrado para este contrato")
    horas_extra_service.eliminar_registro(db, registro)

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id
from app.models import ProvisionVacaciones
from app.schemas.vacaciones import ProvisionVacacionesOut, VacacionTomadaCreate
from app.services import contratos_service, vacaciones_service

router = APIRouter(tags=["vacaciones"])


@router.get(
    "/contratos/{contrato_id}/provisiones-vacaciones",
    response_model=list[ProvisionVacacionesOut],
)
def listar_provisiones_vacaciones(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[ProvisionVacaciones]:
    contratos_service.obtener_contrato(db, contrato_id)
    return vacaciones_service.listar_provisiones(db, contrato_id)


@router.post(
    "/contratos/{contrato_id}/vacaciones-tomadas",
    response_model=ProvisionVacacionesOut,
    status_code=201,
)
def registrar_vacacion_tomada(
    contrato_id: uuid.UUID,
    body: VacacionTomadaCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> ProvisionVacaciones:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return vacaciones_service.registrar_vacacion_tomada(
        db, empresa_id, contrato, body.dias, body.fecha
    )

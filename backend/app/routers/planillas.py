import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual
from app.models import MovimientoPlanilla, Planilla, Usuario
from app.schemas.planillas import GenerarPlanillaRequest, MovimientoPlanillaOut, PlanillaOut
from app.services import planilla_service

router = APIRouter(tags=["planillas"])


@router.post("/planillas/generar", response_model=PlanillaOut, status_code=201)
def generar_planilla(
    body: GenerarPlanillaRequest,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> Planilla:
    return planilla_service.generar_planilla(
        db,
        empresa_id,
        usuario.id,
        body.tipo,
        body.periodo_inicio,
        body.periodo_fin,
        body.fecha_pago,
    )


@router.get("/planillas/{planilla_id}", response_model=PlanillaOut)
def obtener_planilla(
    planilla_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Planilla:
    return planilla_service.obtener_planilla(db, planilla_id)


@router.get("/planillas/{planilla_id}/movimientos", response_model=list[MovimientoPlanillaOut])
def listar_movimientos(
    planilla_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[MovimientoPlanilla]:
    planilla_service.obtener_planilla(db, planilla_id)
    return planilla_service.listar_movimientos(db, planilla_id)

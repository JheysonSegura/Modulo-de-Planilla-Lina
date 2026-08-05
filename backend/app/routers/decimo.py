import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual
from app.models import Planilla, ProvisionDecimo, Usuario
from app.schemas.decimo import GenerarPagoDecimoRequest, ProvisionDecimoOut
from app.schemas.planillas import PlanillaOut
from app.services import contratos_service, decimo_service

router = APIRouter(tags=["decimo"])


@router.post("/planillas/generar-decimo", response_model=PlanillaOut, status_code=201)
def generar_pago_decimo(
    body: GenerarPagoDecimoRequest,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> Planilla:
    return decimo_service.generar_pago_decimo(
        db, empresa_id, usuario.id, body.cuatrimestre, body.anio, body.fecha_pago
    )


@router.get("/contratos/{contrato_id}/provisiones-decimo", response_model=list[ProvisionDecimoOut])
def listar_provisiones_decimo(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[ProvisionDecimo]:
    contratos_service.obtener_contrato(db, contrato_id)
    return decimo_service.listar_provisiones(db, contrato_id)

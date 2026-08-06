import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual
from app.models import Liquidacion, Usuario
from app.schemas.liquidaciones import GenerarLiquidacionRequest, LiquidacionOut
from app.services import contratos_service, liquidaciones_service

router = APIRouter(tags=["liquidaciones"])


@router.post(
    "/contratos/{contrato_id}/liquidacion",
    response_model=LiquidacionOut,
    status_code=201,
)
def generar_liquidacion(
    contrato_id: uuid.UUID,
    body: GenerarLiquidacionRequest,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> Liquidacion:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return liquidaciones_service.generar_liquidacion(
        db,
        empresa_id,
        contrato,
        body.motivo,
        body.fecha_terminacion,
        usuario_id=usuario.id,
        otras_deducciones=body.otras_deducciones,
        monto_salarios_caidos=body.monto_salarios_caidos,
        referencia_sentencia=body.referencia_sentencia,
        fecha_aviso_renuncia=body.fecha_aviso_renuncia,
    )


@router.get(
    "/contratos/{contrato_id}/liquidaciones",
    response_model=list[LiquidacionOut],
)
def listar_liquidaciones(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[Liquidacion]:
    contratos_service.obtener_contrato(db, contrato_id)
    return liquidaciones_service.listar_liquidaciones(db, contrato_id)


@router.post("/liquidaciones/{liquidacion_id}/pagar", response_model=LiquidacionOut)
def pagar_liquidacion(
    liquidacion_id: uuid.UUID,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> Liquidacion:
    liquidacion = liquidaciones_service.obtener_liquidacion(db, liquidacion_id)
    return liquidaciones_service.pagar_liquidacion(db, empresa_id, usuario.id, liquidacion)

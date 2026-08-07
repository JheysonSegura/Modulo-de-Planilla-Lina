import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id
from app.core.responses import respuesta_archivo
from app.models import ProvisionVacaciones, VacacionTomada
from app.schemas.reportes import FormatoRecibo
from app.schemas.vacaciones import (
    AcumularVacacionesRequest,
    ProvisionVacacionesOut,
    VacacionTomadaCreate,
    VacacionTomadaOut,
)
from app.services import contratos_service, reportes_service, vacaciones_service

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


@router.get(
    "/contratos/{contrato_id}/vacaciones-tomadas",
    response_model=list[VacacionTomadaOut],
)
def listar_vacaciones_tomadas(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[VacacionTomada]:
    contratos_service.obtener_contrato(db, contrato_id)
    return vacaciones_service.listar_eventos_tomados(db, contrato_id)


@router.get("/contratos/{contrato_id}/vacaciones-tomadas/{evento_id}/recibo")
def recibo_vacacion(
    contrato_id: uuid.UUID,
    evento_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    formato: Annotated[FormatoRecibo, Query()] = "pdf",
) -> Response:
    evento = vacaciones_service.obtener_evento_tomado(db, contrato_id, evento_id)
    contexto = reportes_service.armar_recibo_vacacion(db, evento)
    nombre_base = f"recibo-vacaciones-{contexto['empleado_identificacion']}-{contexto['fecha']}"
    if formato == "pdf":
        contenido = reportes_service.render_pdf("recibo_vacacion.html", contexto)
    else:
        contenido = reportes_service.render_excel(
            [contexto], reportes_service.COLUMNAS_RECIBO_VACACION
        )
    return respuesta_archivo(contenido, formato, nombre_base)


@router.post(
    "/contratos/{contrato_id}/vacaciones-acumular",
    response_model=ProvisionVacacionesOut,
    status_code=201,
)
def acumular_periodo_vacaciones(
    contrato_id: uuid.UUID,
    body: AcumularVacacionesRequest,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> ProvisionVacaciones:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return vacaciones_service.acumular_periodo(
        db, empresa_id, contrato, body.fecha_acuerdo, body.notificado_autoridad_trabajo
    )

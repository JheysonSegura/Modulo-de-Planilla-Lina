import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, require_roles
from app.core.responses import respuesta_archivo
from app.models import AuditoriaCambio
from app.schemas.auditoria import AuditoriaCambioOut
from app.schemas.reportes import FormatoAuditoria
from app.services import auditoria_service, reportes_service

router = APIRouter(tags=["auditoria"])


@router.get("/auditoria", response_model=list[AuditoriaCambioOut])
def listar_auditoria(
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
    empleado_id: Annotated[uuid.UUID | None, Query()] = None,
    tabla_afectada: Annotated[str | None, Query()] = None,
    accion: Annotated[str | None, Query()] = None,
) -> list[AuditoriaCambio]:
    return auditoria_service.listar(db, empleado_id, tabla_afectada, accion)


@router.get("/auditoria/exportar")
def exportar_auditoria(
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
    empleado_id: Annotated[uuid.UUID | None, Query()] = None,
    tabla_afectada: Annotated[str | None, Query()] = None,
    accion: Annotated[str | None, Query()] = None,
    formato: Annotated[FormatoAuditoria, Query()] = "excel",
) -> Response:
    eventos = auditoria_service.listar(db, empleado_id, tabla_afectada, accion)
    filas = reportes_service.exportar_auditoria(db, eventos)
    if formato == "excel":
        contenido = reportes_service.render_excel(filas, reportes_service.COLUMNAS_AUDITORIA)
    else:
        contenido = reportes_service.render_csv(filas, reportes_service.COLUMNAS_AUDITORIA)
    return respuesta_archivo(contenido, formato, "auditoria")

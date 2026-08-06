import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, require_roles
from app.models import AuditoriaCambio
from app.schemas.auditoria import AuditoriaCambioOut
from app.services import auditoria_service

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

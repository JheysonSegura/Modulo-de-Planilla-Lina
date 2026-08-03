import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_empresa_activa_id, require_roles
from app.models import Empresa
from app.schemas.empresas import EmpresaOut, EmpresaUpdate
from app.services import empresas_service

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/actual", response_model=EmpresaOut)
def obtener_empresa_actual(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db)],
) -> Empresa:
    return empresas_service.obtener_empresa_activa(db, empresa_id)


@router.patch("/actual", response_model=EmpresaOut)
def actualizar_empresa_actual(
    body: EmpresaUpdate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> Empresa:
    empresa = empresas_service.obtener_empresa_activa(db, empresa_id)
    return empresas_service.actualizar_empresa_activa(db, empresa, body)

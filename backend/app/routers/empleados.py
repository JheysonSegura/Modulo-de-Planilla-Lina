import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id
from app.models import Empleado
from app.schemas.empleados import EmpleadoCreate, EmpleadoOut, EmpleadoUpdate
from app.services import empleados_service

router = APIRouter(prefix="/empleados", tags=["empleados"])


@router.post("", response_model=EmpleadoOut, status_code=201)
def crear_empleado(
    body: EmpleadoCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
) -> Empleado:
    return empleados_service.crear_empleado(db, empresa_id, body)


@router.get("", response_model=list[EmpleadoOut])
def listar_empleados(db: Annotated[Session, Depends(get_db_rls)]) -> list[Empleado]:
    # Deliberadamente SIN "WHERE empresa_id = ...": el aislamiento entre
    # empresas lo hace la política RLS de Postgres a partir de
    # app.empresa_actual (fijado en get_db_rls desde el JWT), no un filtro
    # en este código. Ver CLAUDE.md sección "Multi-tenant / RLS".
    return empleados_service.listar_empleados(db)


@router.get("/{empleado_id}", response_model=EmpleadoOut)
def obtener_empleado(
    empleado_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Empleado:
    return empleados_service.obtener_empleado(db, empleado_id)


@router.patch("/{empleado_id}", response_model=EmpleadoOut)
def actualizar_empleado(
    empleado_id: uuid.UUID,
    body: EmpleadoUpdate,
    db: Annotated[Session, Depends(get_db_rls)],
) -> Empleado:
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    return empleados_service.actualizar_empleado(db, empleado, body)

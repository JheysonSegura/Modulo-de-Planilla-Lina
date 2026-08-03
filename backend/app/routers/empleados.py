from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls
from app.models import Empleado
from app.schemas.empleados import EmpleadoOut

router = APIRouter(prefix="/empleados", tags=["empleados"])


@router.get("", response_model=list[EmpleadoOut])
def listar_empleados(db: Annotated[Session, Depends(get_db_rls)]) -> list[Empleado]:
    # Deliberadamente SIN "WHERE empresa_id = ...": el aislamiento entre
    # empresas lo hace la política RLS de Postgres a partir de
    # app.empresa_actual (fijado en get_db_rls desde el JWT), no un filtro
    # en este código. Ver CLAUDE.md sección "Multi-tenant / RLS".
    return list(db.execute(select(Empleado)).scalars().all())

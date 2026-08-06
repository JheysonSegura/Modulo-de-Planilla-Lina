import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_usuario_actual
from app.models import SalarioMinimoVigente, TasaRiesgoProfesional, TasaVigente, TramoIsr, Usuario
from app.schemas.tasas import (
    SalarioMinimoVigenteOut,
    TasaRiesgoProfesionalOut,
    TasaVigenteOut,
    TramoIsrOut,
)
from app.services import tasas_service

# Tasas nacionales (CLAUDE.md sección 2): no tienen empresa_id ni RLS,
# se comparten entre todas las empresas -- por eso estos endpoints solo
# exigen login (get_usuario_actual), no empresa activa seleccionada.
router = APIRouter(prefix="/tasas", tags=["tasas"])


@router.get("/vigentes", response_model=list[TasaVigenteOut])
def listar_vigentes(
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    tipo_tasa: Annotated[str | None, Query()] = None,
    fecha: Annotated[datetime.date | None, Query()] = None,
) -> list[TasaVigente]:
    return tasas_service.listar_vigentes(db, tipo_tasa, fecha)


@router.get("/isr", response_model=list[TramoIsrOut])
def listar_tramos_isr(
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    fecha: Annotated[datetime.date | None, Query()] = None,
) -> list[TramoIsr]:
    return tasas_service.listar_tramos_isr(db, fecha)


@router.get("/riesgo-profesional", response_model=list[TasaRiesgoProfesionalOut])
def listar_riesgo_profesional(
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    fecha: Annotated[datetime.date | None, Query()] = None,
) -> list[TasaRiesgoProfesional]:
    return tasas_service.listar_riesgo_profesional(db, fecha)


@router.get("/salario-minimo", response_model=list[SalarioMinimoVigenteOut])
def listar_salario_minimo(
    db: Annotated[Session, Depends(get_db)],
    _usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    region: Annotated[str | None, Query()] = None,
    actividad: Annotated[str | None, Query()] = None,
    fecha: Annotated[datetime.date | None, Query()] = None,
) -> list[SalarioMinimoVigente]:
    return tasas_service.listar_salario_minimo(db, region, actividad, fecha)

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_escritura
from app.models import Contrato, HistorialCargo, HistorialSalarial, Usuario
from app.schemas.contratos import (
    CambiarCargoRequest,
    CambiarSalarioRequest,
    ContratoCreate,
    ContratoOut,
    ContratoUpdate,
    HistorialCargoOut,
    HistorialSalarialOut,
    SalarioVigenteOut,
)
from app.services import contratos_service

router = APIRouter(tags=["contratos"])


@router.post("/empleados/{empleado_id}/contratos", response_model=ContratoOut, status_code=201)
def crear_contrato(
    empleado_id: uuid.UUID,
    body: ContratoCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> Contrato:
    return contratos_service.crear_contrato(db, empresa_id, empleado_id, body)


@router.get("/empleados/{empleado_id}/contratos", response_model=list[ContratoOut])
def listar_contratos_de_empleado(
    empleado_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[Contrato]:
    return contratos_service.listar_contratos_de_empleado(db, empleado_id)


@router.get("/contratos/{contrato_id}", response_model=ContratoOut)
def obtener_contrato(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Contrato:
    return contratos_service.obtener_contrato(db, contrato_id)


@router.patch("/contratos/{contrato_id}", response_model=ContratoOut)
def actualizar_contrato(
    contrato_id: uuid.UUID,
    body: ContratoUpdate,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> Contrato:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return contratos_service.actualizar_contrato(db, contrato, body)


@router.post(
    "/contratos/{contrato_id}/salario", response_model=HistorialSalarialOut, status_code=201
)
def cambiar_salario(
    contrato_id: uuid.UUID,
    body: CambiarSalarioRequest,
    db: Annotated[Session, Depends(get_db_rls)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> HistorialSalarial:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return contratos_service.cambiar_salario(db, contrato, body, usuario.id)


@router.get("/contratos/{contrato_id}/historial-salarial", response_model=list[HistorialSalarialOut])
def listar_historial_salarial(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[HistorialSalarial]:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return contratos_service.listar_historial_salarial(db, contrato)


@router.get("/contratos/{contrato_id}/salario-vigente", response_model=SalarioVigenteOut)
def salario_vigente(
    contrato_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    fecha: Annotated[
        datetime.date | None,
        Query(description="Fecha a consultar; por defecto hoy."),
    ] = None,
) -> SalarioVigenteOut:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    fecha_consulta = fecha or datetime.date.today()
    registro = contratos_service.salario_vigente_en_fecha(db, contrato, fecha_consulta)
    return SalarioVigenteOut(
        contrato_id=contrato.id, fecha_consulta=fecha_consulta, salario_base=registro.salario_base
    )


@router.post("/contratos/{contrato_id}/cargo", response_model=HistorialCargoOut, status_code=201)
def cambiar_cargo(
    contrato_id: uuid.UUID,
    body: CambiarCargoRequest,
    db: Annotated[Session, Depends(get_db_rls)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> HistorialCargo:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return contratos_service.cambiar_cargo(db, contrato, body, usuario.id)


@router.get("/contratos/{contrato_id}/historial-cargos", response_model=list[HistorialCargoOut])
def listar_historial_cargos(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[HistorialCargo]:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return contratos_service.listar_historial_cargos(db, contrato)

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, require_escritura
from app.core.uploads import LIMITE_DOCUMENTO, leer_archivo_limitado
from app.models import Empleado
from app.schemas.empleados import EmpleadoCreate, EmpleadoOut, EmpleadoUpdate
from app.services import empleados_service

_TIPOS_DOCUMENTO_PERMITIDOS = {"application/pdf", "image/png", "image/jpeg"}

router = APIRouter(prefix="/empleados", tags=["empleados"])


@router.post("", response_model=EmpleadoOut, status_code=201)
def crear_empleado(
    body: EmpleadoCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
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
    _rol: Annotated[str, Depends(require_escritura)],
) -> Empleado:
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    return empleados_service.actualizar_empleado(db, empleado, body)


@router.put("/{empleado_id}/documento-identificacion", response_model=EmpleadoOut)
async def subir_documento_identificacion(
    empleado_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
    archivo: UploadFile,
) -> Empleado:
    if archivo.content_type not in _TIPOS_DOCUMENTO_PERMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de archivo no soportado: {archivo.content_type}",
        )
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    contenido = await leer_archivo_limitado(archivo, LIMITE_DOCUMENTO)
    return empleados_service.actualizar_documento_identificacion(
        db, empleado, contenido, archivo.content_type, archivo.filename or "documento"
    )


@router.get("/{empleado_id}/documento-identificacion")
def obtener_documento_identificacion(
    empleado_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Response:
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    if empleado.documento_identificacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este empleado no tiene documento de identificación cargado")
    nombre = empleado.documento_identificacion_nombre_archivo or "documento"
    return Response(
        content=empleado.documento_identificacion,
        media_type=empleado.documento_identificacion_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )


@router.put("/{empleado_id}/documento-certificado-medico", response_model=EmpleadoOut)
async def subir_documento_certificado_medico(
    empleado_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
    archivo: UploadFile,
) -> Empleado:
    if archivo.content_type not in _TIPOS_DOCUMENTO_PERMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de archivo no soportado: {archivo.content_type}",
        )
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    contenido = await leer_archivo_limitado(archivo, LIMITE_DOCUMENTO)
    return empleados_service.actualizar_documento_certificado_medico(
        db, empleado, contenido, archivo.content_type, archivo.filename or "documento"
    )


@router.get("/{empleado_id}/documento-certificado-medico")
def obtener_documento_certificado_medico(
    empleado_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Response:
    empleado = empleados_service.obtener_empleado(db, empleado_id)
    if empleado.documento_certificado_medico is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este empleado no tiene certificado médico cargado")
    nombre = empleado.documento_certificado_medico_nombre_archivo or "documento"
    return Response(
        content=empleado.documento_certificado_medico,
        media_type=empleado.documento_certificado_medico_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )

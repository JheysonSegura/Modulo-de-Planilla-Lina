import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_roles
from app.core.responses import respuesta_archivo
from app.core.uploads import LIMITE_EXCEL_MIGRACION, leer_archivo_limitado
from app.models import Usuario
from app.schemas.migracion import (
    MigracionDisponibleOut,
    ResultadoMigracionOut,
    ResultadoValidacionMigracion,
)
from app.services import migracion_service

router = APIRouter(prefix="/empresas/actual/migracion", tags=["migracion"])

_TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _validar_content_type(archivo: UploadFile) -> None:
    if archivo.content_type != _TIPO_EXCEL:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de archivo no soportado: {archivo.content_type}. Debe ser un Excel (.xlsx).",
        )


@router.get("/disponible", response_model=MigracionDisponibleOut)
def disponible(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
) -> MigracionDisponibleOut:
    disponible_bool, motivo = migracion_service.verificar_empresa_disponible(db, empresa_id)
    return MigracionDisponibleOut(disponible=disponible_bool, motivo=motivo)


@router.get("/plantilla")
def plantilla(
    _empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
):
    contenido = migracion_service.generar_plantilla()
    return respuesta_archivo(contenido, "excel", "plantilla-migracion-datos")


@router.post("/validar", response_model=ResultadoValidacionMigracion)
async def validar(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
    archivo: UploadFile,
    fecha_corte: Annotated[datetime.date, Form()],
) -> ResultadoValidacionMigracion:
    _validar_content_type(archivo)
    contenido = await leer_archivo_limitado(archivo, LIMITE_EXCEL_MIGRACION)
    return migracion_service.leer_y_validar(db, empresa_id, contenido, fecha_corte)


@router.post("/confirmar", response_model=ResultadoMigracionOut)
async def confirmar(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
    archivo: UploadFile,
    fecha_corte: Annotated[datetime.date, Form()],
) -> ResultadoMigracionOut:
    _validar_content_type(archivo)
    contenido = await leer_archivo_limitado(archivo, LIMITE_EXCEL_MIGRACION)
    resumen = migracion_service.ejecutar_migracion(db, empresa_id, usuario.id, contenido, fecha_corte)
    return ResultadoMigracionOut(resumen=resumen, fecha_corte=fecha_corte)

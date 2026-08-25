import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, require_escritura
from app.core.uploads import LIMITE_DOCUMENTO, leer_archivo_limitado
from app.models import Ausencia
from app.schemas.ausencias import AusenciaCreate, AusenciaOut
from app.services import ausencias_service, contratos_service

_TIPOS_DOCUMENTO_PERMITIDOS = {"application/pdf", "image/png", "image/jpeg"}

router = APIRouter(tags=["ausencias"])


@router.get(
    "/contratos/{contrato_id}/ausencias",
    response_model=list[AusenciaOut],
)
def listar_ausencias(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[Ausencia]:
    contratos_service.obtener_contrato(db, contrato_id)
    return ausencias_service.listar_ausencias(db, contrato_id)


@router.post(
    "/contratos/{contrato_id}/ausencias",
    response_model=AusenciaOut,
    status_code=201,
)
def registrar_ausencia(
    contrato_id: uuid.UUID,
    body: AusenciaCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> Ausencia:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return ausencias_service.registrar_ausencia(
        db,
        empresa_id,
        contrato,
        body.tipo,
        body.fecha_desde,
        body.fecha_hasta,
        body.certificado_ref,
    )


@router.put("/ausencias/{ausencia_id}/documento", response_model=AusenciaOut)
async def subir_documento_ausencia(
    ausencia_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
    archivo: UploadFile,
) -> Ausencia:
    if archivo.content_type not in _TIPOS_DOCUMENTO_PERMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de archivo no soportado: {archivo.content_type}",
        )
    ausencia = ausencias_service.obtener_ausencia(db, ausencia_id)
    contenido = await leer_archivo_limitado(archivo, LIMITE_DOCUMENTO)
    return ausencias_service.actualizar_documento_constancia(
        db, ausencia, contenido, archivo.content_type, archivo.filename or "documento"
    )


@router.get("/ausencias/{ausencia_id}/documento")
def obtener_documento_ausencia(
    ausencia_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Response:
    ausencia = ausencias_service.obtener_ausencia(db, ausencia_id)
    if ausencia.documento_constancia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta ausencia no tiene documento cargado")
    nombre = ausencia.documento_constancia_nombre_archivo or "documento"
    return Response(
        content=ausencia.documento_constancia,
        media_type=ausencia.documento_constancia_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )

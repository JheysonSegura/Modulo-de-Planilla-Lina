import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db_rls, get_empresa_activa_id, get_usuario_actual, require_escritura
from app.core.uploads import LIMITE_DOCUMENTO, leer_archivo_limitado
from app.models import Usuario
from app.schemas.descuentos import (
    CerrarDescuentoRequest,
    CuotaDescuentoOut,
    DescuentoCreate,
    DescuentoOut,
    SimulacionDescuentoOut,
    SimularDescuentoRequest,
)
from app.services import contratos_service, descuentos_service

_TIPOS_DOCUMENTO_PERMITIDOS = {"application/pdf", "image/png", "image/jpeg"}

router = APIRouter(tags=["descuentos"])


@router.get("/contratos/{contrato_id}/descuentos", response_model=list[DescuentoOut])
def listar_descuentos(
    contrato_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[DescuentoOut]:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return descuentos_service.listar_descuentos(db, contrato)


@router.post(
    "/contratos/{contrato_id}/descuentos/simular", response_model=SimulacionDescuentoOut
)
def simular_descuento(
    contrato_id: uuid.UUID,
    body: SimularDescuentoRequest,
    db: Annotated[Session, Depends(get_db_rls)],
) -> SimulacionDescuentoOut:
    contratos_service.obtener_contrato(db, contrato_id)
    return descuentos_service.simular(
        body.frecuencia,
        body.fecha_inicio,
        monto_total=body.monto_total,
        plazo_meses=body.plazo_meses,
        cuota=body.cuota,
        numero_cuotas=body.numero_cuotas,
    )


@router.post(
    "/contratos/{contrato_id}/descuentos", response_model=DescuentoOut, status_code=201
)
def registrar_descuento(
    contrato_id: uuid.UUID,
    body: DescuentoCreate,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> DescuentoOut:
    contrato = contratos_service.obtener_contrato(db, contrato_id)
    return descuentos_service.registrar_descuento(db, empresa_id, usuario.id, contrato, body)


@router.get("/descuentos/{descuento_id}/cuotas", response_model=list[CuotaDescuentoOut])
def listar_cuotas(
    descuento_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> list[CuotaDescuentoOut]:
    descuento = descuentos_service.obtener_descuento(db, descuento_id)
    return descuentos_service.listar_cuotas(db, descuento)


@router.post("/descuentos/{descuento_id}/cerrar", response_model=DescuentoOut)
def cerrar_descuento(
    descuento_id: uuid.UUID,
    body: CerrarDescuentoRequest,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> DescuentoOut:
    descuento = descuentos_service.obtener_descuento(db, descuento_id)
    contrato = contratos_service.obtener_contrato(db, descuento.contrato_id)
    return descuentos_service.cerrar_descuento(
        db, empresa_id, usuario.id, descuento, contrato, body.motivo, body.fecha_cierre
    )


@router.delete("/descuentos/{descuento_id}", status_code=204)
def eliminar_descuento(
    descuento_id: uuid.UUID,
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
) -> Response:
    descuento = descuentos_service.obtener_descuento(db, descuento_id)
    contrato = contratos_service.obtener_contrato(db, descuento.contrato_id)
    descuentos_service.eliminar_descuento(db, empresa_id, usuario.id, descuento, contrato)
    return Response(status_code=204)


@router.put("/descuentos/{descuento_id}/documento", response_model=DescuentoOut)
async def subir_documento_descuento(
    descuento_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_rls)],
    _rol: Annotated[str, Depends(require_escritura)],
    archivo: UploadFile,
) -> DescuentoOut:
    if archivo.content_type not in _TIPOS_DOCUMENTO_PERMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de archivo no soportado: {archivo.content_type}",
        )
    descuento = descuentos_service.obtener_descuento(db, descuento_id)
    contrato = contratos_service.obtener_contrato(db, descuento.contrato_id)
    contenido = await leer_archivo_limitado(archivo, LIMITE_DOCUMENTO)
    return descuentos_service.actualizar_documento(
        db, descuento, contrato, contenido, archivo.content_type, archivo.filename or "documento"
    )


@router.get("/descuentos/{descuento_id}/documento")
def obtener_documento_descuento(
    descuento_id: uuid.UUID, db: Annotated[Session, Depends(get_db_rls)]
) -> Response:
    descuento = descuentos_service.obtener_descuento(db, descuento_id)
    if descuento.documento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este descuento no tiene documento cargado")
    nombre = descuento.documento_nombre_archivo or "documento"
    return Response(
        content=descuento.documento,
        media_type=descuento.documento_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )

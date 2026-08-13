import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_empresa_activa_id, require_puede_crear_empresas, require_roles
from app.models import Empresa, Usuario
from app.schemas.empresas import EmpresaCreateRequest, EmpresaOut, EmpresaUpdate
from app.services import empresas_service

_TIPOS_LOGO_PERMITIDOS = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear_empresa(
    body: EmpresaCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[Usuario, Depends(require_puede_crear_empresas)],
) -> Empresa:
    return empresas_service.crear_empresa(db, body, usuario.id)


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


@router.put("/actual/logo", response_model=EmpresaOut)
async def subir_logo_empresa(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db)],
    _rol: Annotated[str, Depends(require_roles("admin"))],
    archivo: UploadFile,
) -> Empresa:
    if archivo.content_type not in _TIPOS_LOGO_PERMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de imagen no soportado: {archivo.content_type}",
        )
    empresa = empresas_service.obtener_empresa_activa(db, empresa_id)
    contenido = await archivo.read()
    return empresas_service.actualizar_logo(db, empresa, contenido, archivo.content_type)


@router.get("/actual/logo")
def obtener_logo_empresa(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    empresa = empresas_service.obtener_empresa_activa(db, empresa_id)
    if empresa.logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta empresa no tiene logo cargado")
    return Response(content=empresa.logo, media_type=empresa.logo_content_type or "image/png")

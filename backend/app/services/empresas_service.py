import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Empresa
from app.repositories import empresas as empresas_repo
from app.schemas.empresas import EmpresaUpdate


def obtener_empresa_activa(db: Session, empresa_id: uuid.UUID) -> Empresa:
    empresa = empresas_repo.get(db, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return empresa


def actualizar_empresa_activa(db: Session, empresa: Empresa, data: EmpresaUpdate) -> Empresa:
    cambios = data.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(empresa, campo, valor)
    db.commit()
    return empresa


def actualizar_logo(db: Session, empresa: Empresa, contenido: bytes, content_type: str) -> Empresa:
    """Fase 16: logo para el membrete de recibos/reportes. Se guarda en
    la propia tabla empresas (bytea) -- no hay volumen de archivos en
    docker-compose.yml, y así queda consistente con el resto de datos
    de la empresa."""
    empresa.logo = contenido
    empresa.logo_content_type = content_type
    db.commit()
    return empresa

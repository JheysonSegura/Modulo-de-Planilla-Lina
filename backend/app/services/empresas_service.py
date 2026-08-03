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

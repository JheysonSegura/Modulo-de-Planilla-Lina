import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Empresa, UsuarioEmpresa
from app.repositories import empresas as empresas_repo
from app.repositories import usuarios_empresas as usuarios_empresas_repo
from app.schemas.empresas import EmpresaCreateRequest, EmpresaUpdate
from app.services import auditoria_service


def obtener_empresa_activa(db: Session, empresa_id: uuid.UUID) -> Empresa:
    empresa = empresas_repo.get(db, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return empresa


def crear_empresa(db: Session, data: EmpresaCreateRequest, creador_id: uuid.UUID) -> Empresa:
    """Superadmin o un admin con el permiso delegado puede_crear_empresas
    (ver require_puede_crear_empresas). El creador queda SIEMPRE vinculado
    como admin de la empresa nueva: un admin delegado no tiene el bypass
    de seleccionar_empresa que sí tiene un superadmin, así que sin este
    vínculo quedaría bloqueado fuera de la empresa que acaba de crear.
    Para un superadmin es inofensivo (ya tenía acceso igual) y de paso
    lo hace visible en el listado de usuarios de esa empresa."""
    empresa = Empresa(
        razon_social=data.razon_social,
        nombre_comercial=data.nombre_comercial,
        ruc=data.ruc,
        dv=data.dv,
    )
    try:
        empresas_repo.crear(db, empresa)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe una empresa con ese RUC"
        ) from exc

    admin_rol = usuarios_empresas_repo.get_rol_por_nombre(db, "admin")
    usuarios_empresas_repo.crear(
        db, UsuarioEmpresa(usuario_id=creador_id, empresa_id=empresa.id, rol_id=admin_rol.id)
    )

    # auditoria_cambios tiene RLS forzado por empresa_id; todavía no hay
    # ninguna sesión de empresa activa en este punto (se está creando la
    # empresa misma), así que se fija a mano -- mismo truco que
    # tests/conftest.py::crear_empleado.
    db.execute(
        text("SELECT set_config('app.empresa_actual', :eid, true)"),
        {"eid": str(empresa.id)},
    )
    auditoria_service.registrar(
        db,
        empresa.id,
        creador_id,
        "empresas",
        empresa.id,
        "empresa_creada",
        datos_nuevos={"razon_social": empresa.razon_social, "ruc": empresa.ruc},
    )

    db.commit()
    return empresa


def actualizar_empresa_activa(db: Session, empresa: Empresa, data: EmpresaUpdate) -> Empresa:
    cambios = data.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(empresa, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe una empresa con ese RUC"
        ) from exc
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

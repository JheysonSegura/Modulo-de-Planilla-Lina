import uuid
from typing import Annotated, Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decodificar_token
from app.models import Usuario
from app.repositories import empresas as empresas_repo
from app.repositories import usuarios as usuarios_repo

bearer_scheme = HTTPBearer(auto_error=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_claims_actuales(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    try:
        claims = decodificar_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    if claims.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Se requiere un access token")
    return claims


def get_usuario_actual(
    claims: Annotated[dict, Depends(get_claims_actuales)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    usuario = usuarios_repo.get_by_id(db, uuid.UUID(claims["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido o inactivo")
    return usuario


def get_empresa_activa_id(
    claims: Annotated[dict, Depends(get_claims_actuales)],
) -> uuid.UUID:
    """El empresa_id SIEMPRE sale del access token (firmado por el server
    al validar membresía en /auth/seleccionar-empresa), nunca de un header,
    query param o body que mande el cliente — eso es lo que hace imposible
    "hacer trampa" cambiando el empresa_id de la request."""
    empresa_id = claims.get("empresa_id")
    if not empresa_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "No hay una empresa activa seleccionada. Llama a POST /auth/seleccionar-empresa.",
        )
    return uuid.UUID(empresa_id)


def get_rol_activo(claims: Annotated[dict, Depends(get_claims_actuales)]) -> str | None:
    return claims.get("rol")


def get_db_rls(
    empresa_id: Annotated[uuid.UUID, Depends(get_empresa_activa_id)],
    rol_activo: Annotated[str | None, Depends(get_rol_activo)],
    db: Annotated[Session, Depends(get_db)],
) -> Session:
    """Sesión de BD con app.empresa_actual y app.rol_activo fijados para
    esta transacción (equivalente a SET LOCAL, vía set_config con
    is_local=true). A partir de aquí el aislamiento entre empresas y el
    bloqueo de escritura para el rol 'consulta' los hacen las políticas
    RLS de Postgres, no solo el código de la ruta (require_escritura)."""
    db.execute(
        text("SELECT set_config('app.empresa_actual', :empresa_id, true)"),
        {"empresa_id": str(empresa_id)},
    )
    db.execute(
        text("SELECT set_config('app.rol_activo', :rol, true)"),
        {"rol": rol_activo or ""},
    )
    return db


def require_roles(*roles_permitidos: str):
    def dependency(rol: Annotated[str | None, Depends(get_rol_activo)]) -> str:
        if rol not in roles_permitidos:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "No tienes permiso para realizar esta acción"
            )
        return rol

    return dependency


# admin y contador tienen acceso operativo completo (crear y corregir);
# consulta es el único rol sin ningún permiso de escritura. Ver
# CLAUDE.md sección de roles para el razonamiento completo.
require_escritura = require_roles("admin", "contador")


def require_superadmin(usuario: Annotated[Usuario, Depends(get_usuario_actual)]) -> Usuario:
    """Bandera GLOBAL (usuarios.es_superadmin), separada de los roles por
    empresa de require_roles -- ver CLAUDE.md. Protege GET/PATCH /usuarios
    (gestionar el permiso puede_crear_empresas de otros usuarios) -- eso
    NUNCA es delegable, a diferencia de crear empresas."""
    if not usuario.es_superadmin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Requiere privilegios de superadmin"
        )
    return usuario


def require_puede_crear_empresas(
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
) -> Usuario:
    """Protege POST /empresas: superadmin siempre puede, o un usuario con
    el permiso delegado usuarios.puede_crear_empresas (togglable solo por
    un superadmin vía PATCH /usuarios/{id}) -- ver CLAUDE.md."""
    if not (usuario.es_superadmin or usuario.puede_crear_empresas):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "No tienes permiso para crear empresas"
        )
    return usuario


def require_admin_de_empresa(
    empresa_id: uuid.UUID,
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """Protege /mis-empresas/{empresa_id}/usuarios/*: primero exige el
    permiso de plataforma (es_superadmin o puede_crear_empresas, igual que
    require_puede_crear_empresas), y además que sea admin real de ESA
    empresa puntual -- consultado directo a la BD (no del JWT, que solo
    conoce la empresa activa), ya que acá `empresa_id` llega por la URL."""
    if not (usuario.es_superadmin or usuario.puede_crear_empresas):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "No tienes permiso para gestionar accesos entre empresas"
        )
    if usuario.es_superadmin:
        return usuario
    membresia = empresas_repo.get_membresia_activa(db, usuario.id, empresa_id)
    rol = empresas_repo.get_rol(db, membresia.rol_id) if membresia else None
    if rol is None or rol.nombre != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No eres admin de esa empresa")
    return usuario


def get_db_rls_empresa(
    empresa_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Session:
    """Variante de get_db_rls para rutas donde `empresa_id` viene de la URL
    en vez de la empresa activa del JWT (ver require_admin_de_empresa) --
    necesaria porque auditoria_cambios tiene RLS forzado por empresa_id, y
    aquí nunca pasa por /auth/seleccionar-empresa."""
    db.execute(
        text("SELECT set_config('app.empresa_actual', :empresa_id, true)"),
        {"empresa_id": str(empresa_id)},
    )
    db.execute(text("SELECT set_config('app.rol_activo', 'admin', true)"))
    return db

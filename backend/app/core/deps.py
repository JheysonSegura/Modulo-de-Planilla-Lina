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
    db: Annotated[Session, Depends(get_db)],
) -> Session:
    """Sesión de BD con app.empresa_actual fijado para esta transacción
    (equivalente a SET LOCAL, vía set_config con is_local=true). A partir
    de aquí el aislamiento entre empresas lo hacen las políticas RLS de
    Postgres, no un WHERE empresa_id=... en el código de la ruta."""
    db.execute(
        text("SELECT set_config('app.empresa_actual', :empresa_id, true)"),
        {"empresa_id": str(empresa_id)},
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

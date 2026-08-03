import uuid

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.models import Usuario
from app.repositories import empresas as empresas_repo
from app.repositories import refresh_tokens as refresh_tokens_repo
from app.repositories import usuarios as usuarios_repo


def autenticar(db: Session, email: str, password: str) -> Usuario:
    usuario = usuarios_repo.get_by_email(db, email)
    credenciales_invalidas = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas"
    )
    if usuario is None or not usuario.activo:
        raise credenciales_invalidas
    if not security.verify_password(password, usuario.password_hash):
        raise credenciales_invalidas
    return usuario


def emitir_tokens(
    db: Session,
    usuario_id: uuid.UUID,
    empresa_id: uuid.UUID | None = None,
    rol: str | None = None,
) -> tuple[str, str]:
    access_token, _, _ = security.crear_access_token(usuario_id, empresa_id, rol)
    refresh_token, jti, expira = security.crear_refresh_token(usuario_id, empresa_id, rol)
    refresh_tokens_repo.crear(db, usuario_id, jti, expira)
    db.commit()
    return access_token, refresh_token


def listar_empresas(db: Session, usuario_id: uuid.UUID) -> list[dict]:
    filas = empresas_repo.listar_empresas_de_usuario(db, usuario_id)
    return [
        {
            "empresa_id": empresa.id,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial,
            "rol": rol.nombre,
        }
        for _membresia, empresa, rol in filas
    ]


def seleccionar_empresa(
    db: Session, usuario_id: uuid.UUID, empresa_id: uuid.UUID
) -> tuple[str, str]:
    membresia = empresas_repo.get_membresia_activa(db, usuario_id, empresa_id)
    if membresia is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes acceso a esa empresa")
    rol = empresas_repo.get_rol(db, membresia.rol_id)
    return emitir_tokens(db, usuario_id, empresa_id, rol.nombre if rol else None)


def _decodificar_refresh(refresh_token: str) -> dict:
    try:
        claims = security.decodificar_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido")
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Se requiere un refresh token")
    return claims


def refrescar(db: Session, refresh_token: str) -> tuple[str, str]:
    claims = _decodificar_refresh(refresh_token)
    jti = uuid.UUID(claims["jti"])

    registro = refresh_tokens_repo.get_vigente(db, jti)
    if registro is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revocado o expirado")

    usuario_id = uuid.UUID(claims["sub"])
    usuario = usuarios_repo.get_by_id(db, usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inválido o inactivo")

    # Revalida membresía por si el acceso a la empresa cambió desde que se
    # emitió el token; no confía ciegamente en el claim viejo.
    rol_nombre = None
    empresa_id_claim = claims.get("empresa_id")
    empresa_id = uuid.UUID(empresa_id_claim) if empresa_id_claim else None
    if empresa_id is not None:
        membresia = empresas_repo.get_membresia_activa(db, usuario_id, empresa_id)
        if membresia is None:
            empresa_id = None
        else:
            rol = empresas_repo.get_rol(db, membresia.rol_id)
            rol_nombre = rol.nombre if rol else None

    refresh_tokens_repo.revocar(db, jti)
    return emitir_tokens(db, usuario_id, empresa_id, rol_nombre)


def cerrar_sesion(db: Session, refresh_token: str) -> None:
    try:
        claims = security.decodificar_token(refresh_token)
    except jwt.PyJWTError:
        return  # ya inválido/expirado, nada que revocar
    jti = claims.get("jti")
    if jti:
        refresh_tokens_repo.revocar(db, uuid.UUID(jti))
        db.commit()

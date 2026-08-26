import datetime
import logging
import uuid

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.logging_config import LOGGER_SEGURIDAD
from app.models import Usuario
from app.repositories import empresas as empresas_repo
from app.repositories import refresh_tokens as refresh_tokens_repo
from app.repositories import usuarios as usuarios_repo

logger = logging.getLogger(LOGGER_SEGURIDAD)


def autenticar(db: Session, email: str, password: str, ip: str | None = None) -> Usuario:
    # Auditoría de seguridad 2026-08-25 (hallazgo M5): sin esto no había
    # ningún registro de intentos de login fallidos -- necesario para
    # detectar fuerza bruta/credential stuffing (ver también C2, rate
    # limiting). Nunca se loguea la contraseña.
    usuario = usuarios_repo.get_by_email(db, email)
    credenciales_invalidas = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas"
    )
    if usuario is None or not usuario.activo:
        logger.warning("Login fallido (usuario inexistente/inactivo): email=%s ip=%s", email, ip)
        raise credenciales_invalidas
    if not security.verify_password(password, usuario.password_hash):
        logger.warning("Login fallido (contraseña incorrecta): email=%s ip=%s", email, ip)
        raise credenciales_invalidas
    if (
        usuario.debe_cambiar_password
        and usuario.password_temporal_expira is not None
        and usuario.password_temporal_expira < datetime.datetime.now(datetime.timezone.utc)
    ):
        logger.warning("Login fallido (temporal expirada): email=%s ip=%s", email, ip)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "La contraseña temporal expiró. Pedile a un administrador que la restablezca de nuevo.",
        )
    return usuario


def cambiar_password_temporal(
    db: Session, usuario: Usuario, password_actual: str, password_nueva: str
) -> tuple[str, str]:
    if not usuario.debe_cambiar_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Tu contraseña no requiere cambio obligatorio."
        )
    if not security.verify_password(password_actual, usuario.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La contraseña actual no es correcta.")
    if password_actual == password_nueva:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La nueva contraseña debe ser distinta de la temporal.",
        )
    usuario.password_hash = security.hash_password(password_nueva)
    usuario.debe_cambiar_password = False
    usuario.password_temporal_expira = None
    refresh_tokens_repo.revocar_todos_de_usuario(db, usuario.id)
    db.commit()
    return emitir_tokens(db, usuario.id)


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


def listar_empresas(db: Session, usuario: Usuario) -> list[dict]:
    if usuario.es_superadmin:
        # Ve TODAS las empresas activas del sistema, no solo las
        # vinculadas en usuarios_empresas -- "rol": "superadmin" es una
        # etiqueta cosmética para la UI, no un rol real de la tabla roles.
        return [
            {
                "empresa_id": empresa.id,
                "razon_social": empresa.razon_social,
                "nombre_comercial": empresa.nombre_comercial,
                "rol": "superadmin",
            }
            for empresa in empresas_repo.listar_todas_activas(db)
        ]
    filas = empresas_repo.listar_empresas_de_usuario(db, usuario.id)
    return [
        {
            "empresa_id": empresa.id,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial,
            "rol": rol.nombre,
        }
        for _membresia, empresa, rol in filas
    ]


def seleccionar_empresa(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> tuple[str, str]:
    membresia = empresas_repo.get_membresia_activa(db, usuario.id, empresa_id)
    if membresia is None:
        if not usuario.es_superadmin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes acceso a esa empresa")
        empresa = empresas_repo.get(db, empresa_id)
        if empresa is None or not empresa.activo:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    # El superadmin opera SIEMPRE como admin, incluso si por alguna
    # razón tuviera una membresía explícita con otro rol -- ver
    # CLAUDE.md sección de superadmin.
    if usuario.es_superadmin:
        rol_nombre = "admin"
    else:
        rol = empresas_repo.get_rol(db, membresia.rol_id)
        rol_nombre = rol.nombre if rol else None

    return emitir_tokens(db, usuario.id, empresa_id, rol_nombre)


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
        if membresia is None and not usuario.es_superadmin:
            empresa_id = None
        elif usuario.es_superadmin:
            rol_nombre = "admin"
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

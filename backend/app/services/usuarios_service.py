import datetime
import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.logging_config import LOGGER_SEGURIDAD
from app.models import Usuario
from app.repositories import refresh_tokens as refresh_tokens_repo
from app.repositories import usuarios as usuarios_repo
from app.schemas.usuarios import UsuarioAdminOut
from app.services import auditoria_service

logger = logging.getLogger(LOGGER_SEGURIDAD)

# Vigencia de una contraseña temporal generada por un reset (ver
# resetear_password) -- pasado este plazo sin usarla, autenticar()
# rechaza el login aunque la contraseña sea correcta.
PASSWORD_TEMPORAL_VIGENCIA = datetime.timedelta(hours=24)


def _a_out(usuario) -> UsuarioAdminOut:
    return UsuarioAdminOut.model_validate(usuario)


def listar_admins(db: Session) -> list[UsuarioAdminOut]:
    return [_a_out(u) for u in usuarios_repo.listar_admins_globales(db)]


def actualizar_permiso_crear_empresas(
    db: Session, usuario_id: uuid.UUID, valor: bool
) -> UsuarioAdminOut:
    usuario = usuarios_repo.get_by_id(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    usuario.puede_crear_empresas = valor
    db.commit()
    return _a_out(usuario)


def resetear_password(
    db: Session, usuario: Usuario, actor_id: uuid.UUID, empresa_id: uuid.UUID | None
) -> tuple[str, datetime.datetime]:
    """Genera una contraseña temporal, fuerza su cambio en el próximo
    login y revoca las sesiones activas del usuario. Reusada por el
    reset de superadmin (sin empresa, ver resetear_password_superadmin)
    y por el de un admin de empresa (con empresa_id, para auditoría --
    ver usuarios_empresas_service.resetear_password)."""
    password_temporal = security.generar_password_temporal()
    expira_en = datetime.datetime.now(datetime.timezone.utc) + PASSWORD_TEMPORAL_VIGENCIA
    usuario.password_hash = security.hash_password(password_temporal)
    usuario.debe_cambiar_password = True
    usuario.password_temporal_expira = expira_en
    refresh_tokens_repo.revocar_todos_de_usuario(db, usuario.id)
    if empresa_id is not None:
        auditoria_service.registrar(
            db, empresa_id, actor_id, "usuarios", usuario.id, "password_reseteado"
        )
    db.commit()
    # Auditoría de seguridad 2026-08-25 (hallazgo M5): complementa el
    # registro de auditoria_cambios (que no siempre aplica -- ver el
    # `if empresa_id is not None` arriba, el reset de superadmin no tiene
    # empresa) con un log de seguridad uniforme para los 3 endpoints de
    # reset. Nunca la contraseña temporal, solo que hubo un reset.
    logger.info(
        "Password reseteado: usuario_id=%s actor_id=%s empresa_id=%s",
        usuario.id, actor_id, empresa_id,
    )
    return password_temporal, expira_en


def resetear_password_superadmin(
    db: Session, usuario_id: uuid.UUID, actor_id: uuid.UUID
) -> tuple[str, datetime.datetime]:
    if usuario_id == actor_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No podés resetear tu propia contraseña desde acá.",
        )
    usuario = usuarios_repo.get_by_id(db, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return resetear_password(db, usuario, actor_id, empresa_id=None)

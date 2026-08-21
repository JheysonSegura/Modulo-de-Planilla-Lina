import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken


def crear(
    db: Session, usuario_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime.datetime
) -> RefreshToken:
    token = RefreshToken(usuario_id=usuario_id, jti=jti, expires_at=expires_at)
    db.add(token)
    return token


def get_vigente(db: Session, jti: uuid.UUID) -> RefreshToken | None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if token is None or token.revoked_at is not None:
        return None
    if token.expires_at < datetime.datetime.now(datetime.timezone.utc):
        return None
    return token


def revocar(db: Session, jti: uuid.UUID) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.datetime.now(datetime.timezone.utc)


def revocar_todos_de_usuario(db: Session, usuario_id: uuid.UUID) -> None:
    """Cierra todas las sesiones activas del usuario -- usado al resetear
    su contraseña (ver usuarios_service.resetear_password) y al definir
    la contraseña permanente (auth_service.cambiar_password_temporal)."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.usuario_id == usuario_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.datetime.now(datetime.timezone.utc))
    )

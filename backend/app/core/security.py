import datetime
import secrets
import uuid
from typing import Literal

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Sin 0/O/1/l/I -- se le puede dictar al usuario por teléfono/chat sin
# ambigüedad. Usado solo para contraseñas temporales de reset (ver
# usuarios_service.resetear_password), nunca para tokens/secrets.
_ALFABETO_PASSWORD_TEMPORAL = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def generar_password_temporal(longitud: int = 12) -> str:
    return "".join(secrets.choice(_ALFABETO_PASSWORD_TEMPORAL) for _ in range(longitud))


def _crear_token(
    *,
    tipo: Literal["access", "refresh"],
    usuario_id: uuid.UUID,
    expira_en: datetime.timedelta,
    empresa_id: uuid.UUID | None,
    rol: str | None,
) -> tuple[str, uuid.UUID, datetime.datetime]:
    ahora = datetime.datetime.now(datetime.timezone.utc)
    expiracion = ahora + expira_en
    jti = uuid.uuid4()
    payload: dict = {
        "sub": str(usuario_id),
        "type": tipo,
        "jti": str(jti),
        "iat": ahora,
        "exp": expiracion,
    }
    if empresa_id is not None:
        payload["empresa_id"] = str(empresa_id)
    if rol is not None:
        payload["rol"] = rol
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expiracion


def crear_access_token(
    usuario_id: uuid.UUID,
    empresa_id: uuid.UUID | None = None,
    rol: str | None = None,
) -> tuple[str, uuid.UUID, datetime.datetime]:
    return _crear_token(
        tipo="access",
        usuario_id=usuario_id,
        expira_en=datetime.timedelta(minutes=settings.access_token_expire_minutes),
        empresa_id=empresa_id,
        rol=rol,
    )


def crear_refresh_token(
    usuario_id: uuid.UUID,
    empresa_id: uuid.UUID | None = None,
    rol: str | None = None,
) -> tuple[str, uuid.UUID, datetime.datetime]:
    return _crear_token(
        tipo="refresh",
        usuario_id=usuario_id,
        expira_en=datetime.timedelta(days=settings.refresh_token_expire_days),
        empresa_id=empresa_id,
        rol=rol,
    )


def decodificar_token(token: str) -> dict:
    """Lanza jwt.ExpiredSignatureError / jwt.InvalidTokenError si no es
    válido; el llamador decide cómo traducir eso a una respuesta HTTP."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

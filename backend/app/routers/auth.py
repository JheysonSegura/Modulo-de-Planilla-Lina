from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_claims_actuales, get_db, get_usuario_actual
from app.core.rate_limit import limiter
from app.models import Usuario
from app.schemas.auth import (
    CambiarPasswordTemporalRequest,
    EmpresaAccesoOut,
    LoginRequest,
    MeOut,
    SeleccionarEmpresaRequest,
    TokenResponse,
    UsuarioOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Auditoría de seguridad 2026-08-25 (hallazgo A2): el refresh token vive
# en una cookie httpOnly, no en el body -- invisible para JavaScript,
# así que un XSS futuro no podría robarlo. path="/auth" a propósito: la
# cookie nunca se manda a /planillas, /empleados, etc., solo a los 2
# endpoints que realmente la leen (refresh/logout). Requiere que el
# frontend y la API sean subdominios del mismo dominio registrable (ver
# CLAUDE.md/AUDITORIA-SEGURIDAD-2026-08-25.md) -- SameSite=Strict trata
# esa combinación como "mismo sitio", por eso el navegador la reenvía
# sola sin necesitar CORS con dominios distintos ni un proxy intermedio.
_REFRESH_COOKIE = "refresh_token"
_REFRESH_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    # Antes de A2, el frontend seteaba esta misma cookie él mismo (no
    # httpOnly, path="/", vía useCookie) -- cualquier navegador que
    # todavía la tenga puesta terminaría mandando DOS cookies
    # "refresh_token" (una en path="/", otra en la nueva path="/auth"),
    # ambiguas para el servidor y causando 401 intermitentes según cuál
    # mande primero. Se borra la vieja explícitamente en cada respuesta
    # que emite la nueva, para que la transición se autolimpie sola en
    # el primer login/refresh de cada usuario tras este cambio.
    response.delete_cookie(_REFRESH_COOKIE, path="/")
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.refresh_token_expire_days * 86400,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    ip = request.client.host if request.client else None
    usuario = auth_service.autenticar(db, body.email, body.password, ip)
    access_token, refresh_token = auth_service.emitir_tokens(db, usuario.id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(
    request: Request, response: Response, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No hay sesión activa")
    access_token, nuevo_refresh_token = auth_service.refrescar(db, refresh_token)
    _set_refresh_cookie(response, nuevo_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, response: Response, db: Annotated[Session, Depends(get_db)]
) -> None:
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    auth_service.cerrar_sesion(db, refresh_token)
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)
    # Limpia también el rastro de la cookie pre-A2 (path="/", no
    # httpOnly) -- ver nota en _set_refresh_cookie.
    response.delete_cookie(_REFRESH_COOKIE, path="/")


@router.post("/cambiar-password-temporal", response_model=TokenResponse)
@limiter.limit("5/minute")
def cambiar_password_temporal(
    request: Request,
    response: Response,
    body: CambiarPasswordTemporalRequest,
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    access_token, refresh_token = auth_service.cambiar_password_temporal(
        db, usuario, body.password_actual, body.password_nueva
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.get("/empresas", response_model=list[EmpresaAccesoOut])
def listar_empresas(
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    return auth_service.listar_empresas(db, usuario)


@router.post("/seleccionar-empresa", response_model=TokenResponse)
def seleccionar_empresa(
    response: Response,
    body: SeleccionarEmpresaRequest,
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    access_token, refresh_token = auth_service.seleccionar_empresa(
        db, usuario, body.empresa_id
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=MeOut)
def me(
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    claims: Annotated[dict, Depends(get_claims_actuales)],
) -> MeOut:
    return MeOut(
        usuario=UsuarioOut.model_validate(usuario),
        empresa_activa_id=claims.get("empresa_id"),
        rol_activo=claims.get("rol"),
    )

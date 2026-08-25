from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_claims_actuales, get_db, get_usuario_actual
from app.core.rate_limit import limiter
from app.models import Usuario
from app.schemas.auth import (
    CambiarPasswordTemporalRequest,
    EmpresaAccesoOut,
    LoginRequest,
    LogoutRequest,
    MeOut,
    RefreshRequest,
    SeleccionarEmpresaRequest,
    TokenResponse,
    UsuarioOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request, body: LoginRequest, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    usuario = auth_service.autenticar(db, body.email, body.password)
    access_token, refresh_token = auth_service.emitir_tokens(db, usuario.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(
    request: Request, body: RefreshRequest, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    access_token, refresh_token = auth_service.refrescar(db, body.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, db: Annotated[Session, Depends(get_db)]) -> None:
    auth_service.cerrar_sesion(db, body.refresh_token)


@router.post("/cambiar-password-temporal", response_model=TokenResponse)
@limiter.limit("5/minute")
def cambiar_password_temporal(
    request: Request,
    body: CambiarPasswordTemporalRequest,
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    access_token, refresh_token = auth_service.cambiar_password_temporal(
        db, usuario, body.password_actual, body.password_nueva
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/empresas", response_model=list[EmpresaAccesoOut])
def listar_empresas(
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    return auth_service.listar_empresas(db, usuario)


@router.post("/seleccionar-empresa", response_model=TokenResponse)
def seleccionar_empresa(
    body: SeleccionarEmpresaRequest,
    usuario: Annotated[Usuario, Depends(get_usuario_actual)],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    access_token, refresh_token = auth_service.seleccionar_empresa(
        db, usuario, body.empresa_id
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


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

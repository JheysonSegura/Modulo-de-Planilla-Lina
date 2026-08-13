import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Usuario, UsuarioEmpresa
from app.repositories import empresas as empresas_repo
from app.repositories import usuarios as usuarios_repo
from app.repositories import usuarios_empresas as usuarios_empresas_repo
from app.schemas.usuarios_empresas import UsuarioEmpresaCreate, UsuarioEmpresaOut, UsuarioEmpresaUpdate
from app.services import auditoria_service


def _a_out(row) -> UsuarioEmpresaOut:
    return UsuarioEmpresaOut.model_validate(row, from_attributes=True)


def _quedaria_sin_admin(db: Session, empresa_id: uuid.UUID, vinculo: UsuarioEmpresa) -> bool:
    """True si `vinculo` es HOY el único admin activo de la empresa -- se
    llama con los valores todavía sin modificar (antes de
    usuarios_empresas_repo.actualizar, que muta `vinculo` en sitio)."""
    if not vinculo.activo:
        return False
    rol_vigente = empresas_repo.get_rol(db, vinculo.rol_id)
    if rol_vigente is None or rol_vigente.nombre != "admin":
        return False
    filas = usuarios_empresas_repo.listar_de_empresa(db, empresa_id)
    otros_admins_activos = [f for f in filas if f.rol == "admin" and f.activo and f.id != vinculo.id]
    return len(otros_admins_activos) == 0


def listar(db: Session, empresa_id: uuid.UUID) -> list[UsuarioEmpresaOut]:
    return [_a_out(row) for row in usuarios_empresas_repo.listar_de_empresa(db, empresa_id)]


def agregar_usuario(
    db: Session, empresa_id: uuid.UUID, usuario_actual_id: uuid.UUID, data: UsuarioEmpresaCreate
) -> UsuarioEmpresaOut:
    rol = usuarios_empresas_repo.get_rol_por_nombre(db, data.rol)
    if rol is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Rol inválido: '{data.rol}'."
        )

    usuario = usuarios_repo.get_by_email(db, data.email)
    if usuario is None:
        if not data.nombre_completo or not data.password:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No existe un usuario con el email '{data.email}'. Para crear uno nuevo, "
                "manda nombre_completo y password.",
            )
        usuario = usuarios_repo.crear(
            db,
            Usuario(
                email=data.email,
                password_hash=hash_password(data.password),
                nombre_completo=data.nombre_completo,
            ),
        )

    vinculo_existente = usuarios_empresas_repo.get_por_usuario_y_empresa(db, usuario.id, empresa_id)
    if vinculo_existente is not None:
        if vinculo_existente.activo:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Este usuario ya tiene acceso activo a esta empresa."
            )
        vinculo = usuarios_empresas_repo.actualizar(db, vinculo_existente, rol.id, True)
        accion = "acceso_reactivado"
    else:
        vinculo = usuarios_empresas_repo.crear(
            db, UsuarioEmpresa(usuario_id=usuario.id, empresa_id=empresa_id, rol_id=rol.id)
        )
        accion = "acceso_otorgado"

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_actual_id,
        "usuarios_empresas",
        vinculo.id,
        accion,
        datos_nuevos={"email": data.email, "rol": data.rol},
    )

    db.commit()
    fila = usuarios_empresas_repo.get_out(db, vinculo.id)
    return _a_out(fila)


def actualizar_acceso(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_empresa_id: uuid.UUID,
    usuario_actual_id: uuid.UUID,
    data: UsuarioEmpresaUpdate,
) -> UsuarioEmpresaOut:
    vinculo = usuarios_empresas_repo.get(db, usuario_empresa_id)
    if vinculo is None or vinculo.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Acceso de usuario no encontrado.")
    if vinculo.usuario_id == usuario_actual_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No puedes modificar tu propio acceso (rol o activación) -- pídele a otro "
            "administrador que lo haga, para no bloquearte a ti mismo.",
        )

    rol_id = None
    if data.rol is not None:
        rol = usuarios_empresas_repo.get_rol_por_nombre(db, data.rol)
        if rol is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Rol inválido: '{data.rol}'.")
        rol_id = rol.id

    # Una empresa nunca puede quedarse sin ningún admin activo -- ver
    # CLAUDE.md. El autobloqueo (arriba) ya cubre que alguien se quite su
    # propio acceso; esto cubre que un TERCERO (típicamente un superadmin,
    # que puede entrar a cualquier empresa) desactive o degrade al último
    # admin que le queda a la empresa.
    quitaria_admin = data.activo is False or (data.rol is not None and data.rol != "admin")
    if quitaria_admin and _quedaria_sin_admin(db, empresa_id, vinculo):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esta persona es la única admin activa de la empresa -- asigna otro admin "
            "antes de desactivarla o cambiarle el rol.",
        )

    estado_anterior = {"rol_id": vinculo.rol_id, "activo": vinculo.activo}
    usuarios_empresas_repo.actualizar(db, vinculo, rol_id, data.activo)

    if data.activo is False:
        accion = "acceso_revocado"
    elif data.activo is True:
        accion = "acceso_reactivado"
    else:
        accion = "rol_cambiado"

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_actual_id,
        "usuarios_empresas",
        vinculo.id,
        accion,
        datos_anteriores=estado_anterior,
        datos_nuevos={"rol_id": vinculo.rol_id, "activo": vinculo.activo},
    )

    db.commit()
    fila = usuarios_empresas_repo.get_out(db, vinculo.id)
    return _a_out(fila)

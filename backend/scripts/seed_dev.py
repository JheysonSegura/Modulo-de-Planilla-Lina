"""Seed de datos de desarrollo: empresa y usuario de prueba.

Uso (dentro del contenedor backend, o localmente con DATABASE_URL
apuntando a la BD de desarrollo):

    python -m scripts.seed_dev

Deliberadamente NO es una migración de Alembic: son datos de prueba
para desarrollo local, no datos de referencia legal, y no deben poder
terminar en staging/producción por un `alembic upgrade head` corrido
sin cuidado. Requiere que `alembic upgrade head` ya se haya corrido
(necesita la tabla `roles` sembrada).
"""
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Empresa, Rol, Usuario, UsuarioEmpresa

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

EMPRESA_RUC = "0-0-0-DEV"
USUARIO_EMAIL = "dev@nomina.internal"  # ".local" es un TLD reservado (RFC 6762), pydantic.EmailStr lo rechaza
USUARIO_PASSWORD = "dev12345"


def run() -> None:
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        empresa = session.scalar(select(Empresa).where(Empresa.ruc == EMPRESA_RUC))
        if empresa is None:
            empresa = Empresa(
                razon_social="Empresa de Prueba S.A.",
                nombre_comercial="Empresa Demo",
                ruc=EMPRESA_RUC,
                dv="00",
                numero_patronal_css="000-0000-0000",
                clase_riesgo="II",
                moneda="USD",
            )
            session.add(empresa)
            session.flush()
            print(f"Empresa creada: {empresa.id}")
        else:
            print(f"Empresa ya existe: {empresa.id}")

        usuario = session.scalar(select(Usuario).where(Usuario.email == USUARIO_EMAIL))
        if usuario is None:
            usuario = Usuario(
                email=USUARIO_EMAIL,
                password_hash=pwd_context.hash(USUARIO_PASSWORD),
                nombre_completo="Usuario de Desarrollo",
            )
            session.add(usuario)
            session.flush()
            print(f"Usuario creado: {usuario.id} (password: {USUARIO_PASSWORD})")
        else:
            print(f"Usuario ya existe: {usuario.id}")

        admin_rol = session.scalar(select(Rol).where(Rol.nombre == "admin"))
        if admin_rol is None:
            raise RuntimeError(
                "No existe el rol 'admin'. Corre 'alembic upgrade head' primero."
            )

        vinculo = session.scalar(
            select(UsuarioEmpresa).where(
                UsuarioEmpresa.usuario_id == usuario.id,
                UsuarioEmpresa.empresa_id == empresa.id,
            )
        )
        if vinculo is None:
            vinculo = UsuarioEmpresa(
                usuario_id=usuario.id,
                empresa_id=empresa.id,
                rol_id=admin_rol.id,
            )
            session.add(vinculo)
            print("Vínculo usuario-empresa creado con rol 'admin'.")
        else:
            print("El vínculo usuario-empresa ya existe.")

        session.commit()


if __name__ == "__main__":
    run()

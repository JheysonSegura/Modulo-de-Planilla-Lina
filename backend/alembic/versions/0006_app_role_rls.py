"""Rol de aplicación de bajo privilegio + FORCE ROW LEVEL SECURITY

Motivo: el rol que corre las migraciones (settings.database_url_admin,
por defecto 'nomina') es el dueño de las tablas y, en la imagen oficial
de Postgres, además queda como SUPERUSER (es el rol de bootstrap del
contenedor). Postgres NUNCA aplica políticas RLS a superusuarios ni al
dueño de la tabla (salvo con FORCE, y FORCE tampoco afecta a un
superusuario) — así que si la app siguiera conectándose con ese mismo
rol, las políticas de migracion_multiempresa.sql existirían pero jamás
se aplicarían.

Esta migración crea un rol separado, sin SUPERUSER/BYPASSRLS, que es
el que la app usa en tiempo de ejecución (settings.database_url), y
fuerza RLS en las tablas protegidas como defensa en profundidad.

Revision ID: 0006_app_role_rls
Revises: 0005_refresh_tokens
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.engine import make_url

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0006_app_role_rls"
down_revision: Union[str, None] = "0005_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = settings.postgres_app_user
ADMIN_ROLE = make_url(settings.database_url_admin).username


def _escaped_password() -> str:
    # Contraseña de desarrollo gestionada por variable de entorno
    # (POSTGRES_APP_PASSWORD); no es un secreto de producción real.
    return settings.postgres_app_password.replace("'", "''")


def upgrade() -> None:
    password = _escaped_password()
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{password}'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            ELSE
                ALTER ROLE {APP_ROLE} PASSWORD '{password}'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;

        GRANT USAGE ON SCHEMA public TO {APP_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};

        ALTER DEFAULT PRIVILEGES FOR ROLE {ADMIN_ROLE} IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES FOR ROLE {ADMIN_ROLE} IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE};

        -- empleados/contratos/planillas ya tienen ENABLE ROW LEVEL SECURITY
        -- (migración 0002). FORCE es defensa en profundidad por si alguna
        -- vez cambia el dueño de la tabla; con nomina_app -que ya no es
        -- dueño ni superusuario- las políticas aplican de todas formas.
        ALTER TABLE empleados FORCE ROW LEVEL SECURITY;
        ALTER TABLE contratos FORCE ROW LEVEL SECURITY;
        ALTER TABLE planillas FORCE ROW LEVEL SECURITY;
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE empleados NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE contratos NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE planillas NO FORCE ROW LEVEL SECURITY;

        ALTER DEFAULT PRIVILEGES FOR ROLE {ADMIN_ROLE} IN SCHEMA public
            REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};
        ALTER DEFAULT PRIVILEGES FOR ROLE {ADMIN_ROLE} IN SCHEMA public
            REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE};

        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE};
        REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};
        DROP OWNED BY {APP_ROLE};
        DROP ROLE IF EXISTS {APP_ROLE};
        """
    )

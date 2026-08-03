"""Tabla refresh_tokens (permite logout/revocación real de JWT)

No existe en db/schema_nomina_panama.sql: es infraestructura de
autenticación de la app, no dato de negocio de una empresa, por eso no
lleva empresa_id ni RLS.

Revision ID: 0005_refresh_tokens
Revises: 0004_seed_roles
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_refresh_tokens"
down_revision: Union[str, None] = "0004_seed_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            usuario_id  UUID NOT NULL REFERENCES usuarios(id),
            jti         UUID NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked_at  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_refresh_tokens_usuario ON refresh_tokens(usuario_id);
        CREATE INDEX idx_refresh_tokens_jti ON refresh_tokens(jti);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens;")

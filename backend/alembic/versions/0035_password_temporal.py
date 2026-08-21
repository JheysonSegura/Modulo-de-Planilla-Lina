"""Reset de contraseña por admin/superadmin: contraseña temporal + cambio
forzado en el próximo login.

Hasta ahora no existía ningún mecanismo de "olvidé mi contraseña" -- ni
self-service ni administrado. Esta migración agrega el soporte de datos
para que un admin de empresa o un superadmin puedan resetear la
contraseña de un usuario (ver usuarios_service.resetear_password): se
genera una temporal que vence en 24h (password_temporal_expira) y que
obliga al usuario a definir una nueva permanente antes de poder usar
cualquier otro endpoint (debe_cambiar_password, ver
deps.py::get_usuario_actual). Ver CLAUDE.md.

Revision ID: 0035_password_temporal
Revises: 0034_puede_crear_empresas
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035_password_temporal"
down_revision: Union[str, None] = "0034_puede_crear_empresas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN debe_cambiar_password BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE usuarios ADD COLUMN password_temporal_expira TIMESTAMPTZ NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS password_temporal_expira")
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS debe_cambiar_password")

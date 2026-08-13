"""Superadmin de plataforma: bandera global en usuarios

usuarios.es_superadmin es una bandera GLOBAL (no un rol por empresa
como los de usuarios_empresas) que permite crear empresas nuevas y
operar como admin en cualquier empresa sin necesidad de estar
vinculado a ella en usuarios_empresas -- ver CLAUDE.md. No lleva RLS:
la tabla usuarios ya es global (no tiene empresa_id). No se otorga
desde la app; solo con scripts/otorgar_superadmin.py.

Revision ID: 0033_superadmin
Revises: 0032_liquidacion_constancia
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033_superadmin"
down_revision: Union[str, None] = "0032_liquidacion_constancia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN es_superadmin BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS es_superadmin")

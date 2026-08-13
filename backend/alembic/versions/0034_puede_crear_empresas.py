"""Permiso delegado: usuarios.puede_crear_empresas

A diferencia de usuarios.es_superadmin (solo otorgable por script), esta
bandera SÍ es togglable desde la app -- pero únicamente por un
superadmin, vía GET/PATCH /usuarios (require_superadmin). Permite que
un admin puntual cree empresas nuevas (POST /empresas) sin darle el
resto de los poderes de superadmin (no ve todas las empresas, no entra
a empresas ajenas). Ver CLAUDE.md sección de superadmin.

Revision ID: 0034_puede_crear_empresas
Revises: 0033_superadmin
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034_puede_crear_empresas"
down_revision: Union[str, None] = "0033_superadmin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN puede_crear_empresas BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS puede_crear_empresas")

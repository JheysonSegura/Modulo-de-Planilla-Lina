"""Agrega tamano_empresa a salario_minimo_vigente y empresas

El Decreto Ejecutivo N.13 de 31-dic-2025 (Gaceta Oficial N.30438) divide
varias actividades económicas por tamaño de empresa (pequeña/gran), con
un umbral de empleados que varía por sector (11/15/16 según la
actividad). En vez de modelar el umbral, se agrega un campo manual --
igual que region/actividad_economica en 0008 -- que el admin declara a
nivel empresa: 'Pequeña Empresa' o 'Gran Empresa'. La lógica de
resolución vive en app/services/salario_minimo_service.py.

Revision ID: 0017_tamano_empresa
Revises: 0016_rls_provisiones_decimo
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_tamano_empresa"
down_revision: Union[str, None] = "0016_rls_provisiones_decimo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE salario_minimo_vigente ADD COLUMN tamano_empresa VARCHAR(50);
        ALTER TABLE empresas ADD COLUMN tamano_empresa VARCHAR(50);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE empresas DROP COLUMN IF EXISTS tamano_empresa;
        ALTER TABLE salario_minimo_vigente DROP COLUMN IF EXISTS tamano_empresa;
        """
    )

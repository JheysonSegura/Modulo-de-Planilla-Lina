"""Logo de empresa (Fase 16)

Columna nueva en empresas para el logo que se imprime en recibos y
reportes (junto con RUC/DV/dirección/teléfono, que ya existían en el
modelo pero no se usaban en ningún documento hasta ahora). Se guarda
como bytea en la propia tabla -- no hay volumen de archivos en
docker-compose.yml y así queda consistente con el aislamiento RLS que
ya tiene el resto de la tabla, sin infraestructura nueva.

Revision ID: 0026_empresa_logo
Revises: 0025_auditoria_seguridad
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_empresa_logo"
down_revision: Union[str, None] = "0025_auditoria_seguridad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE empresas ADD COLUMN logo BYTEA;
        ALTER TABLE empresas ADD COLUMN logo_content_type VARCHAR(50);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE empresas DROP COLUMN IF EXISTS logo_content_type;
        ALTER TABLE empresas DROP COLUMN IF EXISTS logo;
        """
    )

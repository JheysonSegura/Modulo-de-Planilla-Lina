"""Agrega region y actividad_economica a empresas

El Código de Trabajo / Decreto Ejecutivo N.13 fija el salario mínimo por
región y actividad económica, no un valor único nacional (CLAUDE.md
sección 4). Hasta ahora salario_minimo_vigente no tenía forma de saber
a qué empresa aplicarle cada fila cuando hay más de una vigente a la
vez para la misma fecha. Estos dos campos son el vínculo que faltaba;
la lógica de resolución vive en app/services/salario_minimo_service.py.

Van en `empresas` (no en `contratos`) siguiendo el mismo patrón que
`clase_riesgo`, que ya está ahí para las tasas de riesgo profesional:
la actividad económica registrada es del establecimiento, no del
puesto individual.

Revision ID: 0008_empresa_region_actividad
Revises: 0007_seed_salario_minimo
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_empresa_region_actividad"
down_revision: Union[str, None] = "0007_seed_salario_minimo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE empresas ADD COLUMN region VARCHAR(100);
        ALTER TABLE empresas ADD COLUMN actividad_economica VARCHAR(150);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE empresas DROP COLUMN IF EXISTS actividad_economica;
        ALTER TABLE empresas DROP COLUMN IF EXISTS region;
        """
    )

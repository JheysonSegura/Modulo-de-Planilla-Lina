"""Acumulación de hasta 2 períodos de vacaciones (Fase 12, Art. 59 CT)

Agrega notificado_autoridad_trabajo a provisiones_vacaciones: registra
que el acuerdo de acumulación (Art. 59 CT -- requiere acuerdo explícito
empleador-trabajador notificado a la autoridad de trabajo, NO es
automático por el solo paso del tiempo) fue notificado. El sistema no
tramita la notificación real (proceso administrativo externo) -- es un
campo informativo que se marca al capturar el acuerdo. Ver
FASE12-plan-acumulacion-vacaciones.txt.

No se toca RLS (ya existe desde 0020_rls_provisiones_vac).

Revision ID: 0023_acumulacion_vacaciones
Revises: 0022_ausencias
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023_acumulacion_vacaciones"
down_revision: Union[str, None] = "0022_ausencias"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE provisiones_vacaciones
            ADD COLUMN notificado_autoridad_trabajo BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE provisiones_vacaciones DROP COLUMN IF EXISTS notificado_autoridad_trabajo;
        """
    )

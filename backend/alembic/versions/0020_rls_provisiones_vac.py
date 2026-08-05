"""RLS en provisiones_vacaciones (Fase 9)

La tabla existe desde la migración 0001 (con empresa_id agregado en la
0002), pero nunca tuvo política RLS -- mismo caso que
provisiones_decimo antes de la 0016. Como Fase 9 empieza a escribir en
ella activamente (provisión de vacaciones), se agrega ENABLE/FORCE ROW
LEVEL SECURITY + política de aislamiento por empresa_id, mismo patrón
que 0016_rls_provisiones_decimo.

Revision ID: 0020_rls_provisiones_vac
Revises: 0019_seed_riesgo_profesional
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_rls_provisiones_vac"
down_revision: Union[str, None] = "0019_seed_riesgo_profesional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE provisiones_vacaciones ENABLE ROW LEVEL SECURITY;
        ALTER TABLE provisiones_vacaciones FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_provisiones_vacaciones ON provisiones_vacaciones
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_provisiones_vacaciones ON provisiones_vacaciones;
        ALTER TABLE provisiones_vacaciones NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE provisiones_vacaciones DISABLE ROW LEVEL SECURITY;
        """
    )

"""RLS en provisiones_decimo (Fase 8)

La tabla existe desde la migración 0001 (con empresa_id agregado en la
0002), pero nunca tuvo política RLS -- a diferencia de
empleados/contratos/planillas, que sí la tienen desde la 0002/0006.
Como Fase 8 empieza a escribir en ella activamente (provisión mensual
del décimo tercer mes), se agrega ENABLE/FORCE ROW LEVEL SECURITY +
política de aislamiento por empresa_id, mismo patrón que
registro_horas_extra (0011) y conceptos_variables_pendientes (0012).

Revision ID: 0016_rls_provisiones_decimo
Revises: 0015_seed_decimo_isr
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_rls_provisiones_decimo"
down_revision: Union[str, None] = "0015_seed_decimo_isr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE provisiones_decimo ENABLE ROW LEVEL SECURITY;
        ALTER TABLE provisiones_decimo FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_provisiones_decimo ON provisiones_decimo
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_provisiones_decimo ON provisiones_decimo;
        ALTER TABLE provisiones_decimo NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE provisiones_decimo DISABLE ROW LEVEL SECURITY;
        """
    )

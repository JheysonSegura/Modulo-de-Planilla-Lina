"""Columnas faltantes + RLS en liquidaciones (Fase 10)

La tabla liquidaciones existe desde el schema base (migración 0001)
con columnas para decimo_proporcional/vacaciones_pendientes/preaviso/
indemnizacion/otras_deducciones, pero le faltaban dos conceptos
legales reales (Código de Trabajo, Título VI):

- salario_pendiente: días trabajados del período en curso que aún no
  se pagaron vía planilla regular.
- prima_antiguedad (Art. 224 CT): 1 semana de salario por año
  laborado, OBLIGATORIA para todo contrato POR TIEMPO INDEFINIDO sin
  importar el motivo de terminación -- es un concepto legal distinto
  de la indemnización del Art. 225 (que solo aplica a despido
  injustificado/renuncia justificada/causa económica). Mezclarlos en
  la misma columna perdería trazabilidad para el contador.

Además, la tabla nunca tuvo política RLS -- mismo hueco que tenían
provisiones_decimo (antes de 0016) y provisiones_vacaciones (antes de
0020). Como Fase 10 empieza a escribir en ella activamente, se agrega
aquí también.

Revision ID: 0021_liquidaciones
Revises: 0020_rls_provisiones_vac
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_liquidaciones"
down_revision: Union[str, None] = "0020_rls_provisiones_vac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE liquidaciones ADD COLUMN salario_pendiente NUMERIC(12,2) NOT NULL DEFAULT 0;
        ALTER TABLE liquidaciones ADD COLUMN prima_antiguedad NUMERIC(12,2) NOT NULL DEFAULT 0;

        ALTER TABLE liquidaciones ENABLE ROW LEVEL SECURITY;
        ALTER TABLE liquidaciones FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_liquidaciones ON liquidaciones
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_liquidaciones ON liquidaciones;
        ALTER TABLE liquidaciones NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE liquidaciones DISABLE ROW LEVEL SECURITY;

        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS prima_antiguedad;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS salario_pendiente;
        """
    )

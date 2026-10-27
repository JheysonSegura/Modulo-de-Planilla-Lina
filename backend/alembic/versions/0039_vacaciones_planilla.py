"""vacaciones_tomadas: fecha_fin_goce + movimiento_planilla_id + anulada

Hasta ahora registrar una vacación tomada solo calculaba el bruto (días ×
salario/30), sin CSS/SE/ISR ni aportes patronales, y las quincenas que
caían dentro del descanso igual pagaban el salario completo (doble pago).
Decisión del usuario 2026-10-23 (ver PLAN-vacaciones-descuentos.md): cada
toma genera su propia Planilla tipo='vacaciones' (mismo flujo que el
décimo: borrador -> aprobar -> pagar) con un MovimientoPlanilla que lleva
los descuentos de ley, y ese pago REEMPLAZA el salario de esos días en las
quincenas regulares.

- fecha_fin_goce: último día del descanso (fecha + días - 1, días
  calendario). `fecha` pasa a significar formalmente "inicio del descanso".
- movimiento_planilla_id: el movimiento de la planilla de vacaciones que
  pagó esta toma. NULL en las filas viejas (anteriores a este cambio), que
  siguen mostrando su recibo sin descuentos como antes.
- anulada: true si la planilla de vacaciones se anuló (los días se
  devolvieron al saldo).

planillas.tipo es VARCHAR(20) sin CHECK, así que el nuevo valor
'vacaciones' no requiere alterar esa columna.

Revision ID: 0039_vacaciones_planilla
Revises: 0038_horas_extra_aplicado
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039_vacaciones_planilla"
down_revision: Union[str, None] = "0038_horas_extra_aplicado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE vacaciones_tomadas ADD COLUMN fecha_fin_goce DATE;
        UPDATE vacaciones_tomadas
            SET fecha_fin_goce = fecha + (CEIL(dias_tomados)::int - 1);
        ALTER TABLE vacaciones_tomadas ALTER COLUMN fecha_fin_goce SET NOT NULL;
        ALTER TABLE vacaciones_tomadas
            ADD COLUMN movimiento_planilla_id UUID REFERENCES movimientos_planilla(id);
        ALTER TABLE vacaciones_tomadas ADD COLUMN anulada BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE vacaciones_tomadas DROP COLUMN IF EXISTS anulada;
        ALTER TABLE vacaciones_tomadas DROP COLUMN IF EXISTS movimiento_planilla_id;
        ALTER TABLE vacaciones_tomadas DROP COLUMN IF EXISTS fecha_fin_goce;
        """
    )

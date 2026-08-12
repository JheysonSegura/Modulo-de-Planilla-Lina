"""Constancia bancaria del pago de una liquidación

Mismo patrón exacto que 0030_planillas_constancia_pago.py: la
liquidación pasa por un flujo de estados igual al de planillas
(borrador -> aprobada/anulada -> pagada), y confirmar el pago exige
subir la constancia bancaria. El documento se sirve aparte vía
GET /liquidaciones/{id}/constancia-pago, nunca inline en LiquidacionOut.

Revision ID: 0032_liquidacion_constancia
Revises: 0031_rol_activo_rls_consulta
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032_liquidacion_constancia"
down_revision: Union[str, None] = "0031_rol_activo_rls_consulta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE liquidaciones ADD COLUMN documento_constancia_pago BYTEA;
        ALTER TABLE liquidaciones ADD COLUMN documento_constancia_pago_content_type VARCHAR(50);
        ALTER TABLE liquidaciones ADD COLUMN documento_constancia_pago_nombre_archivo VARCHAR(255);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS documento_constancia_pago_nombre_archivo;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS documento_constancia_pago_content_type;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS documento_constancia_pago;
        """
    )

"""Constancia bancaria obligatoria al confirmar el pago de una planilla

El estado 'pagada' (vocabulario reservado desde el schema original,
`db/schema_nomina_panama.sql`) nunca tuvo una transición real: aprobar
solo llevaba a 'procesada'. Se agrega el documento como bytea en la
propia tabla, mismo patrón que ausencias.documento_constancia
(0029_ausencias_documento) y los documentos de empleado
(0028_datos_personales_empleados): servido aparte por endpoint
dedicado, nunca inline en PlanillaOut.

Revision ID: 0030_planillas_constancia_pago
Revises: 0029_ausencias_documento
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030_planillas_constancia_pago"
down_revision: Union[str, None] = "0029_ausencias_documento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE planillas ADD COLUMN documento_constancia_pago BYTEA;
        ALTER TABLE planillas ADD COLUMN documento_constancia_pago_content_type VARCHAR(50);
        ALTER TABLE planillas ADD COLUMN documento_constancia_pago_nombre_archivo VARCHAR(255);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE planillas DROP COLUMN IF EXISTS documento_constancia_pago_nombre_archivo;
        ALTER TABLE planillas DROP COLUMN IF EXISTS documento_constancia_pago_content_type;
        ALTER TABLE planillas DROP COLUMN IF EXISTS documento_constancia_pago;
        """
    )

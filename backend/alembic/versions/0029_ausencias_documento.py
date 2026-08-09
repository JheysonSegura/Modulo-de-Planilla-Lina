"""Documento de constancia opcional por ausencia (Fase 18)

`ausencias.certificado_ref` ya existía como referencia de texto libre
("relevante por afiliación migrante", ver 0022_ausencias.py) pero nunca
permitió cargar el documento real. Se agrega el documento como bytea en la
propia tabla, mismo patrón que empresas.logo (0026_empresa_logo) y los
documentos de empleado (0028_datos_personales_empleados): servido aparte
por endpoint dedicado, nunca inline en AusenciaOut.

Revision ID: 0029_ausencias_documento
Revises: 0028_datos_personales_empleados
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029_ausencias_documento"
down_revision: Union[str, None] = "0028_datos_personales_empleados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ausencias ADD COLUMN documento_constancia BYTEA;
        ALTER TABLE ausencias ADD COLUMN documento_constancia_content_type VARCHAR(50);
        ALTER TABLE ausencias ADD COLUMN documento_constancia_nombre_archivo VARCHAR(255);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ausencias DROP COLUMN IF EXISTS documento_constancia_nombre_archivo;
        ALTER TABLE ausencias DROP COLUMN IF EXISTS documento_constancia_content_type;
        ALTER TABLE ausencias DROP COLUMN IF EXISTS documento_constancia;
        """
    )

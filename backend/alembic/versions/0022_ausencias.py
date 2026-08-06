"""Tabla ausencias + RLS (Fase 11)

Nueva tabla para registrar ausencias/incapacidades de un contrato
(Art. 199/200/208 del Código de Trabajo). Se resta de los cálculos de
décimo y vacaciones en decimo_service/vacaciones_service, cada tipo
con su propio tratamiento -- ver FASE11-plan-ausencias.txt para el
catálogo completo y las fuentes legales verificadas contra
código-detrabajo.pdf.

RLS habilitado desde el inicio (a diferencia de provisiones_decimo/
provisiones_vacaciones/liquidaciones, que lo agregaron después en
migraciones separadas cuando el código empezó a escribir en ellas
activamente) -- esta tabla nace ya con código que la usa desde el
día uno.

Revision ID: 0022_ausencias
Revises: 0021_liquidaciones
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_ausencias"
down_revision: Union[str, None] = "0021_liquidaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ausencias (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            contrato_id      UUID NOT NULL REFERENCES contratos(id),
            tipo             VARCHAR(30) NOT NULL,
            fecha_desde      DATE NOT NULL,
            fecha_hasta      DATE NOT NULL,
            certificado_ref  VARCHAR(100),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            empresa_id       UUID REFERENCES empresas(id)
        );

        ALTER TABLE ausencias ENABLE ROW LEVEL SECURITY;
        ALTER TABLE ausencias FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_ausencias ON ausencias
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS ausencias;
        """
    )

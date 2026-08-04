"""Tabla parametros_isr: parámetro nacional (no por empresa, CLAUDE.md
sección 2) que decide si el décimo tercer mes se integra a la base
gravable del ISR o se trata como exento. Vigencia por fecha, mismo
patrón que tasas_vigentes/tramos_isr.

Deliberadamente SIN NINGUNA FILA SEMBRADA: el tratamiento del décimo
en el ISR tiene fuentes contradictorias (CLAUDE.md sección 6) y no se
confirma con el contador todavía. Mientras no exista una fila vigente,
app/services/planilla_service.py trata el décimo como
'no_configurado' (no se suma a la base, pero se marca explícitamente
distinto de 'exento' para no confundir un valor no confirmado con una
decisión legal ya tomada). Sembrar el valor real es una migración de
una sola fila, no requiere tocar código.

Revision ID: 0014_parametros_isr
Revises: 0013_isr_auditoria_movimientos
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_parametros_isr"
down_revision: Union[str, None] = "0013_isr_auditoria_movimientos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE parametros_isr (
            id                                SERIAL PRIMARY KEY,
            decimo_incluido_en_base_gravable   BOOLEAN NOT NULL,
            fecha_inicio                       DATE NOT NULL,
            fecha_fin                          DATE,
            fuente_legal                       VARCHAR(150),
            created_at                         TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_parametros_isr_fecha ON parametros_isr(fecha_inicio);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS parametros_isr;")

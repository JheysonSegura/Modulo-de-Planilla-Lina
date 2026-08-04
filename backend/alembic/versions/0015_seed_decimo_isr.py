"""Seed de parametros_isr: décimo integrado a la base del ISR

Confirmado por el contador de la empresa el 2026-08-04, con un caso
numérico verificado end-to-end (ver FASE7-plan-isr.txt y CLAUDE.md
sección 5):

    Salario $2,500/mes -> renta bruta anual con décimo (13 meses)
    $32,500 -> excedente sobre $11,000 = $21,500 -> 15% = $3,225.00
    anual -> $268.75/mes.

Esto también confirmó que la base gravable del ISR NO resta CSS/SE
antes de aplicar los tramos (a diferencia de lo que documentaba
originalmente CLAUDE.md sección 6) -- ese cambio vive en
app/services/planilla_service.py, no en esta migración.

fecha_inicio se ancla a 2025-01-01 por consistencia con las demás
tasas/tramos ya sembrados (migración 0003).

Revision ID: 0015_seed_decimo_isr
Revises: 0014_parametros_isr
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_seed_decimo_isr"
down_revision: Union[str, None] = "0014_parametros_isr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_BASE = "2025-01-01"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO parametros_isr
            (decimo_incluido_en_base_gravable, fecha_inicio, fecha_fin, fuente_legal)
        VALUES
            (true, '{FECHA_BASE}', NULL,
             'Confirmado por el contador de la empresa (2026-08-04): el décimo tercer mes '
             'se integra a la base anualizada del ISR como un mes adicional de salario.');
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM parametros_isr WHERE fecha_inicio = '{FECHA_BASE}';")

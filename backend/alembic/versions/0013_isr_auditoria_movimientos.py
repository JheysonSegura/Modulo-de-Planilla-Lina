"""Columnas de auditoría ISR en movimientos_planilla (Fase 7)

isr_retenido ya existía (Fase 6, placeholder en 0). Estas columnas
guardan los valores intermedios del cálculo -- renta anual proyectada,
impuesto anual proyectado, tratamiento del décimo usado, número de
período fiscal y períodos restantes -- para que cada movimiento sea
reconstruible a mano sin adivinar qué fórmula se aplicó. Crítico dado
que este módulo necesita validación del contador antes de producción
(ver CLAUDE.md sección 6 y app/services/planilla_service.py).

Todas nullable: no rompe las filas ya generadas en Fase 6 (donde
isr_retenido era siempre 0 sin este desglose).

Revision ID: 0013_isr_auditoria_movimientos
Revises: 0012_conceptos_var_pendientes
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_isr_auditoria_movimientos"
down_revision: Union[str, None] = "0012_conceptos_var_pendientes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE movimientos_planilla
            ADD COLUMN isr_renta_anual_proyectada NUMERIC(12,2),
            ADD COLUMN isr_impuesto_anual_proyectado NUMERIC(12,2),
            ADD COLUMN isr_decimo_tratamiento VARCHAR(20),
            ADD COLUMN isr_numero_periodo_anio SMALLINT,
            ADD COLUMN isr_periodos_restantes_anio SMALLINT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE movimientos_planilla
            DROP COLUMN IF EXISTS isr_periodos_restantes_anio,
            DROP COLUMN IF EXISTS isr_numero_periodo_anio,
            DROP COLUMN IF EXISTS isr_decimo_tratamiento,
            DROP COLUMN IF EXISTS isr_impuesto_anual_proyectado,
            DROP COLUMN IF EXISTS isr_renta_anual_proyectada;
        """
    )

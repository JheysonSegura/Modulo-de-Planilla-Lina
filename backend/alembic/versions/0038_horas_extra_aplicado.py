"""registro_horas_extra: aplicado + movimiento_planilla_id

Hasta ahora una hora extra se podía borrar en cualquier momento, incluso
si ya había sido sumada a una planilla generada/procesada/pagada --
horas_extra_service.py::eliminar_registro no tenía ninguna validación de
esto. planilla_service ya vuelve a sumar TODOS los registros del rango de
fechas cada vez que genera una planilla (sin marcar nada como "ya
consumido"), a diferencia de conceptos_variables_pendientes, que sí tiene
este mismo par de columnas (migración 0012) para no aplicarse dos veces y
para poder revertirse si la planilla que lo aplicó se anula.

Se agrega el mismo par de columnas a registro_horas_extra, mismo patrón:
aplicado=true + movimiento_planilla_id cuando una planilla lo consume,
revertido a false/NULL si esa planilla se anula.

Revision ID: 0038_horas_extra_aplicado
Revises: 0037_historial_cargos
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038_horas_extra_aplicado"
down_revision: Union[str, None] = "0037_historial_cargos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE registro_horas_extra ADD COLUMN aplicado BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE registro_horas_extra
            ADD COLUMN movimiento_planilla_id UUID REFERENCES movimientos_planilla(id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE registro_horas_extra DROP COLUMN IF EXISTS movimiento_planilla_id;
        ALTER TABLE registro_horas_extra DROP COLUMN IF EXISTS aplicado;
        """
    )

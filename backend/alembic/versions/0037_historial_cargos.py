"""Tabla historial_cargos + RLS (trazabilidad de cambios de puesto)

Hasta ahora "cargo" era un campo suelto en contratos, editable vía
PATCH /contratos/{id} con un setattr directo (contratos_service.py::
actualizar_contrato): un cambio de puesto sobrescribia el valor anterior
sin dejar rastro de cuándo cambió ni de cuál era antes, y sin auditar.

Se agrega esta tabla de historial, mismo patrón que historial_salarial +
POST /contratos/{id}/salario (misma vigencia por rango de fechas), pero
sin las validaciones de salario (un cargo no tiene "no puede bajar" ni
salario mínimo). RLS habilitado desde el día uno -- mismo criterio que
0027_vacaciones_tomadas: esta tabla nace ya con código que escribe en
ella activamente, a diferencia del gap histórico que tuvo
historial_salarial (corregido recién en 0036).

Revision ID: 0037_historial_cargos
Revises: 0036_rls_movimientos_historial
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037_historial_cargos"
down_revision: Union[str, None] = "0036_rls_movimientos_historial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE historial_cargos (
            id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            contrato_id           UUID NOT NULL REFERENCES contratos(id),
            cargo                 VARCHAR(150) NOT NULL,
            fecha_vigencia_desde  DATE NOT NULL,
            fecha_vigencia_hasta  DATE,
            motivo                VARCHAR(100),
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            empresa_id            UUID REFERENCES empresas(id)
        );

        CREATE INDEX idx_historial_cargos_contrato ON historial_cargos(contrato_id);

        ALTER TABLE historial_cargos ENABLE ROW LEVEL SECURITY;
        ALTER TABLE historial_cargos FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_historial_cargos ON historial_cargos
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS historial_cargos;
        """
    )

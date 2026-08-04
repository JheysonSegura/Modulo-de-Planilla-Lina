"""Tabla conceptos_variables_pendientes: captura previa de bonos,
comisiones y descuentos puntuales por contrato, ANTES de que exista
una planilla (conceptos_variables.movimiento_planilla_id es NOT NULL,
así que no puede existir un concepto variable sin un movimiento ya
creado). Simétrica a registro_horas_extra (migración 0011): el motor
de planilla (Fase 6, app/services/planilla_service.py) recoge los
pendientes no aplicados de un contrato dentro del rango del período,
los copia a conceptos_variables ligados al movimiento recién creado, y
los marca aplicado=true para que no se dupliquen en una futura corrida.

Revision ID: 0012_conceptos_var_pendientes
Revises: 0011_registro_horas_extra
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
# (id acortado a propósito: alembic_version.version_num es VARCHAR(32)
# y "0012_conceptos_variables_pendientes" lo excede.)
revision: str = "0012_conceptos_var_pendientes"
down_revision: Union[str, None] = "0011_registro_horas_extra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE conceptos_variables_pendientes (
            id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            empresa_id                  UUID NOT NULL REFERENCES empresas(id),
            contrato_id                 UUID NOT NULL REFERENCES contratos(id),
            fecha                       DATE NOT NULL,
            tipo                        VARCHAR(20) NOT NULL,   -- 'ingreso' | 'deduccion'
            codigo                      VARCHAR(50) NOT NULL,   -- 'bono','comision','descuento_puntual', etc.
            descripcion                 TEXT,
            monto                       NUMERIC(12,2) NOT NULL,
            aplicado                    BOOLEAN NOT NULL DEFAULT false,
            movimiento_planilla_id      UUID REFERENCES movimientos_planilla(id),
            registrado_por_usuario_id   UUID REFERENCES usuarios(id),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_conceptos_variables_pendientes_contrato_fecha
            ON conceptos_variables_pendientes(contrato_id, fecha);
        CREATE INDEX idx_conceptos_variables_pendientes_empresa
            ON conceptos_variables_pendientes(empresa_id);

        ALTER TABLE conceptos_variables_pendientes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE conceptos_variables_pendientes FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_conceptos_variables_pendientes
            ON conceptos_variables_pendientes
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_conceptos_variables_pendientes
            ON conceptos_variables_pendientes;
        ALTER TABLE conceptos_variables_pendientes NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE conceptos_variables_pendientes DISABLE ROW LEVEL SECURITY;
        DROP TABLE IF EXISTS conceptos_variables_pendientes;
        """
    )

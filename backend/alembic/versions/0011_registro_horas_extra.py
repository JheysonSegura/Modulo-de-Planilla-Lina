"""Tabla registro_horas_extra: detalle auditable de horas extra por
contrato/día, con el desglose dentro/exceso de límite y los factores
de recargo aplicados en el momento del cálculo (ver CLAUDE.md sección
6 y la migración 0010_seed_recargos_horas_extra para los % usados).

Los campos valor_hora_ordinaria/factor_*/monto_* son snapshots: se
recalculan bajo demanda (alta/edición/baja de un registro en la misma
semana ISO, ver app/services/horas_extra_service.py) pero no se leen
de nuevo automáticamente si cambian las tasas o el salario después,
para que el registro quede trazable igual que historial_salarial.

Revision ID: 0011_registro_horas_extra
Revises: 0010_seed_recargos_horas_extra
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_registro_horas_extra"
down_revision: Union[str, None] = "0010_seed_recargos_horas_extra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE registro_horas_extra (
            id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            empresa_id                  UUID NOT NULL REFERENCES empresas(id),
            contrato_id                 UUID NOT NULL REFERENCES contratos(id),
            fecha                       DATE NOT NULL,
            tipo_hora                   VARCHAR(30) NOT NULL,
                -- 'diurna' | 'nocturna' | 'prolongacion_nocturna' (Art. 33 CT,
                -- 'nocturna' incluye prolongación de mixta iniciada en diurno,
                -- 'prolongacion_nocturna' incluye prolongación de mixta
                -- iniciada en nocturno -- ver CLAUDE.md sección 5)
            tipo_dia                    VARCHAR(30) NOT NULL DEFAULT 'ordinario',
                -- 'ordinario' | 'domingo_descanso' | 'feriado_duelo_nacional'
            horas                       NUMERIC(5,2) NOT NULL,
            horas_dentro_limite         NUMERIC(5,2) NOT NULL DEFAULT 0,
            horas_exceso_limite         NUMERIC(5,2) NOT NULL DEFAULT 0,
            valor_hora_ordinaria        NUMERIC(10,4) NOT NULL DEFAULT 0,
            factor_tipo_hora            NUMERIC(6,4) NOT NULL DEFAULT 0,
            factor_tipo_dia             NUMERIC(6,4) NOT NULL DEFAULT 0,
            factor_exceso_limite        NUMERIC(6,4) NOT NULL DEFAULT 0,
            monto_dentro_limite         NUMERIC(12,2) NOT NULL DEFAULT 0,
            monto_exceso_limite         NUMERIC(12,2) NOT NULL DEFAULT 0,
            monto_calculado             NUMERIC(12,2) NOT NULL DEFAULT 0,
            registrado_por_usuario_id   UUID REFERENCES usuarios(id),
            observaciones               TEXT,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_registro_horas_extra_contrato_fecha
            ON registro_horas_extra(contrato_id, fecha);
        CREATE INDEX idx_registro_horas_extra_empresa
            ON registro_horas_extra(empresa_id);

        -- Misma defensa en profundidad que empleados/contratos/planillas
        -- (migraciones 0002 y 0006): RLS + FORCE, el rol de aplicación
        -- nomina_app no es dueño de la tabla ni superusuario.
        ALTER TABLE registro_horas_extra ENABLE ROW LEVEL SECURITY;
        ALTER TABLE registro_horas_extra FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_registro_horas_extra ON registro_horas_extra
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_registro_horas_extra ON registro_horas_extra;
        ALTER TABLE registro_horas_extra NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE registro_horas_extra DISABLE ROW LEVEL SECURITY;
        DROP TABLE IF EXISTS registro_horas_extra;
        """
    )

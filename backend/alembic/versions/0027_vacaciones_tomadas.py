"""Tabla vacaciones_tomadas + RLS (Fase 16)

Hasta ahora "tomar vacaciones" (vacaciones_service.registrar_vacacion_tomada)
solo mutaba los totales de provisiones_vacaciones (dias_gozados/saldo) en
sitio, sin dejar ningún registro individual de esa toma concreta. Para poder
emitir un recibo de vacaciones por evento (igual que ya existe un recibo
por movimiento_planilla o por liquidación), se agrega esta tabla de
historial: una fila por cada período efectivamente tocado en cada llamada a
registrar_vacacion_tomada (una toma que cruza el período 'acumulado' y el
'abierto' genera 2 filas).

RLS habilitado desde el día uno -- mismo criterio que 0022_ausencias: esta
tabla nace ya con código que escribe en ella activamente, a diferencia del
gap histórico que tuvo auditoria_cambios (corregido recién en 0025).

Revision ID: 0027_vacaciones_tomadas
Revises: 0026_empresa_logo
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_vacaciones_tomadas"
down_revision: Union[str, None] = "0026_empresa_logo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE vacaciones_tomadas (
            id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            provision_id              UUID NOT NULL REFERENCES provisiones_vacaciones(id),
            contrato_id               UUID NOT NULL REFERENCES contratos(id),
            fecha                     DATE NOT NULL,
            dias_tomados              NUMERIC(6, 2) NOT NULL,
            valor_dia                 NUMERIC(12, 2) NOT NULL,
            monto                     NUMERIC(12, 2) NOT NULL,
            dias_acumulados_snapshot  NUMERIC(6, 2) NOT NULL,
            dias_gozados_snapshot     NUMERIC(6, 2) NOT NULL,
            created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
            empresa_id                UUID REFERENCES empresas(id)
        );

        CREATE INDEX idx_vacaciones_tomadas_contrato ON vacaciones_tomadas(contrato_id);

        ALTER TABLE vacaciones_tomadas ENABLE ROW LEVEL SECURITY;
        ALTER TABLE vacaciones_tomadas FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_vacaciones_tomadas ON vacaciones_tomadas
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS vacaciones_tomadas;
        """
    )

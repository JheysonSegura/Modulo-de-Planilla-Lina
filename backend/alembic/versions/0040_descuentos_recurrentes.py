"""Descuentos recurrentes: préstamos, bancos, hipoteca, cooperativa, pensión, embargo

Decisiones del usuario 2026-11-17 (ver PLAN-descuentos-prestamos.md):

- descuentos_recurrentes: un préstamo/descuento por contrato. Con monto y
  plazo (préstamos, hipoteca, embargo con deuda fija) la cuota la calcula
  el sistema (monto ÷ n.º de cuotas, la última absorbe los centavos); sin
  monto (pensión, cooperativa) es una cuota fija indefinida hasta que se
  cierra.
- cuotas_descuento: cada cobro efectivo, ligado al movimiento de planilla
  (quincena/mes o vacaciones) o a la liquidación que lo descontó. El saldo
  NO se guarda: se calcula excluyendo planillas/liquidaciones anuladas,
  así anular una de ellas devuelve la cuota al saldo sin código extra.
- movimientos_planilla.advertencias: avisos de tope (Art. 161 CT) y de
  cuotas cobradas parcialmente por falta de neto. No cambian totales.
- liquidaciones: descuento del préstamo de la empresa (Art. 164 CT), con
  monto manual + observación si el usuario no descuenta el saldo completo.
- tasas_vigentes: topes del Art. 161 CT (nunca hardcodeados en código).

RLS desde el día uno, con las políticas de solo lectura para 'consulta'
(mismo criterio que 0031_rol_activo_rls_consulta).

Revision ID: 0040_descuentos_recurrentes
Revises: 0039_vacaciones_planilla
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040_descuentos_recurrentes"
down_revision: Union[str, None] = "0039_vacaciones_planilla"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_NUEVAS = ["descuentos_recurrentes", "cuotas_descuento"]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE descuentos_recurrentes (
            id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            contrato_id                 UUID NOT NULL REFERENCES contratos(id),
            tipo                        VARCHAR(30) NOT NULL,
            acreedor                    VARCHAR(150) NOT NULL,
            referencia                  VARCHAR(100),
            monto_total                 NUMERIC(12, 2),
            plazo_meses                 INTEGER,
            frecuencia                  VARCHAR(10) NOT NULL,
            numero_cuotas               INTEGER,
            cuota                       NUMERIC(12, 2) NOT NULL,
            fecha_inicio                DATE NOT NULL,
            estado                      VARCHAR(20) NOT NULL DEFAULT 'activo',
            fecha_cierre                DATE,
            motivo_cierre               TEXT,
            observacion                 TEXT,
            documento                   BYTEA,
            documento_content_type      VARCHAR(50),
            documento_nombre_archivo    VARCHAR(255),
            registrado_por_usuario_id   UUID REFERENCES usuarios(id),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            empresa_id                  UUID REFERENCES empresas(id)
        );
        CREATE INDEX idx_descuentos_recurrentes_contrato ON descuentos_recurrentes(contrato_id);

        CREATE TABLE cuotas_descuento (
            id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            descuento_id            UUID NOT NULL REFERENCES descuentos_recurrentes(id),
            movimiento_planilla_id  UUID REFERENCES movimientos_planilla(id),
            liquidacion_id          UUID REFERENCES liquidaciones(id),
            fecha_cobro             DATE NOT NULL,
            monto                   NUMERIC(12, 2) NOT NULL,
            monto_programado        NUMERIC(12, 2) NOT NULL,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            empresa_id              UUID REFERENCES empresas(id),
            CHECK (movimiento_planilla_id IS NOT NULL OR liquidacion_id IS NOT NULL)
        );
        CREATE INDEX idx_cuotas_descuento_descuento ON cuotas_descuento(descuento_id);
        CREATE INDEX idx_cuotas_descuento_movimiento ON cuotas_descuento(movimiento_planilla_id);

        ALTER TABLE descuentos_recurrentes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE descuentos_recurrentes FORCE ROW LEVEL SECURITY;
        CREATE POLICY empresa_aislamiento_descuentos_recurrentes ON descuentos_recurrentes
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);

        ALTER TABLE cuotas_descuento ENABLE ROW LEVEL SECURITY;
        ALTER TABLE cuotas_descuento FORCE ROW LEVEL SECURITY;
        CREATE POLICY empresa_aislamiento_cuotas_descuento ON cuotas_descuento
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);

        ALTER TABLE movimientos_planilla ADD COLUMN advertencias JSONB;

        ALTER TABLE liquidaciones
            ADD COLUMN descuento_prestamo_empresa NUMERIC(12, 2) NOT NULL DEFAULT 0;
        ALTER TABLE liquidaciones
            ADD COLUMN descuento_prestamo_manual BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE liquidaciones ADD COLUMN observacion_descuento_prestamo TEXT;

        INSERT INTO tasas_vigentes (tipo_tasa, tasa, fecha_inicio, fecha_fin, fuente_legal) VALUES
            ('tope_desc_prestamo_empresa', 0.15, '2025-01-01', NULL, 'Código de Trabajo Art. 161.3'),
            ('tope_desc_prestamo_bancario', 0.20, '2025-01-01', NULL, 'Código de Trabajo Art. 161.11'),
            ('tope_desc_hipoteca', 0.30, '2025-01-01', NULL, 'Código de Trabajo Art. 161.4'),
            ('tope_desc_embargo_excedente', 0.15, '2025-01-01', NULL, 'Código de Trabajo Art. 161.7 / 162'),
            ('tope_desc_total', 0.50, '2025-01-01', NULL, 'Código de Trabajo Art. 161.13');
        """
    )
    for tabla in _TABLAS_NUEVAS:
        op.execute(
            f"""
            CREATE POLICY consulta_solo_lectura_insert_{tabla} ON {tabla}
                AS RESTRICTIVE FOR INSERT
                WITH CHECK (current_setting('app.rol_activo', true) IS DISTINCT FROM 'consulta');
            CREATE POLICY consulta_solo_lectura_update_{tabla} ON {tabla}
                AS RESTRICTIVE FOR UPDATE
                USING (current_setting('app.rol_activo', true) IS DISTINCT FROM 'consulta')
                WITH CHECK (current_setting('app.rol_activo', true) IS DISTINCT FROM 'consulta');
            CREATE POLICY consulta_solo_lectura_delete_{tabla} ON {tabla}
                AS RESTRICTIVE FOR DELETE
                USING (current_setting('app.rol_activo', true) IS DISTINCT FROM 'consulta');
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM tasas_vigentes WHERE tipo_tasa IN (
            'tope_desc_prestamo_empresa', 'tope_desc_prestamo_bancario', 'tope_desc_hipoteca',
            'tope_desc_embargo_excedente', 'tope_desc_total'
        );
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS observacion_descuento_prestamo;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS descuento_prestamo_manual;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS descuento_prestamo_empresa;
        ALTER TABLE movimientos_planilla DROP COLUMN IF EXISTS advertencias;
        DROP TABLE IF EXISTS cuotas_descuento;
        DROP TABLE IF EXISTS descuentos_recurrentes;
        """
    )

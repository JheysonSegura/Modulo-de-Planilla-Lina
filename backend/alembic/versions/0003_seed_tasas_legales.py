"""Seed de tasas legales vigentes (CSS, Seguro Educativo, décimo, ISR)

Valores tomados de CLAUDE.md sección 4. La fecha de vigencia inicial
(2025-01-01) se ancla al año de la Ley 462 de 2025; no se afirma que
esas tasas rijan desde antes de esa fecha.

IMPORTANTE - PENDIENTE DE VALIDAR CON CONTADOR:
  - Los tramos de ISR (tramos_isr) son la tabla progresiva documentada
    en CLAUDE.md, pero las cifras exactas están pendientes de validar
    con el contador antes de producción (ver CLAUDE.md sección 4 y 6).
  - salario_minimo_vigente NO se siembra en esta migración: CLAUDE.md
    no documenta montos concretos del Decreto Ejecutivo N.13 (varían
    por región/actividad), así que no se inventan cifras aquí. Cargar
    manualmente cuando se tengan los valores oficiales confirmados.

Revision ID: 0003_seed_tasas_legales
Revises: 0002_multiempresa_rls
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_seed_tasas_legales"
down_revision: Union[str, None] = "0002_multiempresa_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_BASE = "2025-01-01"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO tasas_vigentes (tipo_tasa, tasa, fecha_inicio, fecha_fin, fuente_legal) VALUES
            ('css_empleado', 0.0975, '{FECHA_BASE}', NULL, 'Código de Trabajo / CSS - cuota obrero (fija)'),
            ('css_patronal', 0.1325, '{FECHA_BASE}', '2027-02-28', 'Ley 462 de 2025'),
            ('css_patronal', 0.1425, '2027-03-01', '2029-02-28', 'Ley 462 de 2025'),
            ('css_patronal', 0.1525, '2029-03-01', NULL, 'Ley 462 de 2025'),
            ('seguro_educativo_empleado', 0.0125, '{FECHA_BASE}', NULL, 'Ley de Seguro Educativo'),
            ('seguro_educativo_patronal', 0.0150, '{FECHA_BASE}', NULL, 'Ley de Seguro Educativo'),
            ('decimo_empleado', 0.0725, '{FECHA_BASE}', NULL, 'CSS - cuota especial sobre Décimo Tercer Mes'),
            ('decimo_patronal', 0.1075, '{FECHA_BASE}', NULL, 'CSS - cuota especial sobre Décimo Tercer Mes');

        -- PENDIENTE DE VALIDAR CON CONTADOR ANTES DE PRODUCCIÓN (CLAUDE.md sección 4/6).
        -- Tabla progresiva: exento hasta $11,000 anuales, 15% de 11,001 a 50,000,
        -- 25% sobre el excedente de 50,000. impuesto_base = acumulado de tramos previos.
        INSERT INTO tramos_isr (fecha_inicio, fecha_fin, monto_desde, monto_hasta, tasa_marginal, impuesto_base) VALUES
            ('{FECHA_BASE}', NULL, 0,     11000, 0.00, 0),
            ('{FECHA_BASE}', NULL, 11000, 50000, 0.15, 0),
            ('{FECHA_BASE}', NULL, 50000, NULL,  0.25, 5850);
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM tramos_isr WHERE fecha_inicio = '{FECHA_BASE}';
        DELETE FROM tasas_vigentes WHERE fecha_inicio IN ('{FECHA_BASE}', '2027-03-01', '2029-03-01');
        """
    )

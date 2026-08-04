"""Seed de recargos legales de horas extra en tasas_vigentes

Reutiliza la tabla tasas_vigentes (no crea una tabla de tasas nueva)
para los porcentajes de recargo del Código de Trabajo que aplican al
cálculo en cascada de horas extra (ver CLAUDE.md sección 5 y la
migración 0011_registro_horas_extra). Valores verificados directamente
contra código-detrabajo.pdf (Decreto de Gabinete 252 de 1971, con las
modificaciones de la Ley 44 de 1995):

  - Art. 33 núm. 1: +25% hora extra diurna.
  - Art. 33 núm. 2: +50% hora extra nocturna, o prolongación de jornada
    mixta iniciada en período diurno.
  - Art. 33 núm. 3: +75% prolongación de la nocturna, o de jornada
    mixta iniciada en período nocturno.
  - Art. 48: +50% trabajo en domingo o día de descanso semanal.
  - Art. 49: +150% trabajo en día de fiesta o duelo nacional.
  - Art. 36 núm. 4: +75% adicional sobre el excedente de 3h/día o
    9h/semana de jornada extraordinaria.

fecha_inicio se ancla a 2025-01-01 por consistencia con las demás tasas
sembradas en 0003_seed_tasas_legales (Ley 462): estos artículos del
Código de Trabajo no muestran reformas posteriores a 1995 en el texto
revisado, pero no hay necesidad operativa de recalcular planillas
anteriores a esa fecha.

Revision ID: 0010_seed_recargos_horas_extra
Revises: 0009_exencion_salario_minimo
Create Date: 2026-08-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_seed_recargos_horas_extra"
down_revision: Union[str, None] = "0009_exencion_salario_minimo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_BASE = "2025-01-01"

TIPOS_TASA = (
    "recargo_hextra_diurna",
    "recargo_hextra_nocturna",
    "recargo_hextra_prolongacion_nocturna",
    "recargo_dia_domingo_descanso",
    "recargo_dia_feriado_duelo",
    "recargo_exceso_limite_horas_extra",
)


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO tasas_vigentes (tipo_tasa, tasa, fecha_inicio, fecha_fin, fuente_legal) VALUES
            ('recargo_hextra_diurna', 0.25, '{FECHA_BASE}', NULL,
                'Art. 33 núm. 1 CT (hora extra diurna)'),
            ('recargo_hextra_nocturna', 0.50, '{FECHA_BASE}', NULL,
                'Art. 33 núm. 2 CT (hora extra nocturna, o prolongación de mixta iniciada en diurno)'),
            ('recargo_hextra_prolongacion_nocturna', 0.75, '{FECHA_BASE}', NULL,
                'Art. 33 núm. 3 CT (prolongación de la nocturna, o de mixta iniciada en nocturno)'),
            ('recargo_dia_domingo_descanso', 0.50, '{FECHA_BASE}', NULL,
                'Art. 48 CT (trabajo en domingo o día de descanso semanal obligatorio)'),
            ('recargo_dia_feriado_duelo', 1.50, '{FECHA_BASE}', NULL,
                'Art. 49 CT (trabajo en día de fiesta o duelo nacional)'),
            ('recargo_exceso_limite_horas_extra', 0.75, '{FECHA_BASE}', NULL,
                'Art. 36 núm. 4 CT (excedente sobre 3h/día o 9h/semana de jornada extraordinaria)');
        """
    )


def downgrade() -> None:
    tipos = ", ".join(f"'{t}'" for t in TIPOS_TASA)
    op.execute(
        f"DELETE FROM tasas_vigentes WHERE tipo_tasa IN ({tipos}) AND fecha_inicio = '{FECHA_BASE}';"
    )

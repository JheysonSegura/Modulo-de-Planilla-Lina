"""Extensión de liquidaciones: salarios caídos + penalidad Art. 222 (Fase 13)

- contratos.es_tecnico: determina el aviso de renuncia exigido por el
  Art. 222 CT (15 días normal, 2 meses si es "trabajador técnico").
- liquidaciones.salarios_caidos / referencia_sentencia (Art. 219/220
  CT): captura manual -- depende de una sentencia judicial de
  reintegro que el sistema no puede calcular ni conocer por sí solo.
- liquidaciones.penalidad_renuncia_sin_aviso (Art. 222 CT): 1 semana de
  salario si el trabajador renuncia sin dar el aviso previo exigido.

Ver FASE13-plan-liquidaciones-ext.txt.

Revision ID: 0024_liquidaciones_ext
Revises: 0023_acumulacion_vacaciones
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_liquidaciones_ext"
down_revision: Union[str, None] = "0023_acumulacion_vacaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contratos ADD COLUMN es_tecnico BOOLEAN NOT NULL DEFAULT false;

        ALTER TABLE liquidaciones ADD COLUMN salarios_caidos NUMERIC(12,2) NOT NULL DEFAULT 0;
        ALTER TABLE liquidaciones ADD COLUMN referencia_sentencia VARCHAR(100);
        ALTER TABLE liquidaciones ADD COLUMN penalidad_renuncia_sin_aviso NUMERIC(12,2) NOT NULL DEFAULT 0;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS penalidad_renuncia_sin_aviso;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS referencia_sentencia;
        ALTER TABLE liquidaciones DROP COLUMN IF EXISTS salarios_caidos;

        ALTER TABLE contratos DROP COLUMN IF EXISTS es_tecnico;
        """
    )

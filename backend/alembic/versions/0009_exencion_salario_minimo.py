"""Exención explícita de salario mínimo en contratos (ej. pasantías)

El salario mínimo no aplica igual a todos los contratos: una pasantía
formal o un contrato de aprendizaje puede tener un tratamiento distinto,
pero el Código de Trabajo panameño no define esto de forma tan simple
como para asumirlo automáticamente a partir de tipo_contrato (una
pasantía podría ser 'definido' igual que cualquier otro contrato de
plazo fijo). En vez de inferirlo, se agrega un flag explícito que hay
que marcar a propósito, con un motivo obligatorio -- queda auditable en
el propio contrato, y NO se activa solo. Confirmar con el contador
antes de usarlo como regla general.

El otro caso legítimo de salario por debajo del mínimo (medio tiempo)
NO necesita este flag: se resuelve prorrateando por
contratos.jornada_horas_semana en salario_minimo_service.py.

Revision ID: 0009_exencion_salario_minimo
Revises: 0008_empresa_region_actividad
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_exencion_salario_minimo"
down_revision: Union[str, None] = "0008_empresa_region_actividad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contratos ADD COLUMN exento_salario_minimo BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE contratos ADD COLUMN motivo_exencion_salario_minimo VARCHAR(200);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE contratos DROP COLUMN IF EXISTS motivo_exencion_salario_minimo;
        ALTER TABLE contratos DROP COLUMN IF EXISTS exento_salario_minimo;
        """
    )

"""Seed de salario_minimo_vigente (referencia general, no el desglose oficial completo)

Valor confirmado por el usuario: $605.00 mensual, de referencia para
2026. El Decreto Ejecutivo N.13 en realidad distingue por región y
actividad económica (ver CLAUDE.md sección 4), pero todavía no existe
un campo región en empresas/contratos para poder elegir automáticamente
cuál de varias filas vigentes le aplica a un contrato — por eso se
siembra UNA sola fila nacional en vez del desglose completo. Si más
adelante se cargan filas adicionales para regiones/actividades
distintas con fechas que se superpongan, la validación de
salario_minimo_service.validar_salario_minimo empezará a rechazar por
ambigüedad hasta que se diseñe ese vínculo.

Revision ID: 0007_seed_salario_minimo
Revises: 0006_app_role_rls
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_seed_salario_minimo"
down_revision: Union[str, None] = "0006_app_role_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_INICIO = "2026-01-01"
MONTO_MENSUAL = "605.00"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO salario_minimo_vigente (region, actividad, monto_mensual, fecha_inicio, fecha_fin, decreto_ref)
        VALUES (
            'Nacional',
            NULL,
            {MONTO_MENSUAL},
            '{FECHA_INICIO}',
            NULL,
            'Decreto Ejecutivo N.13 -- referencia general, falta desglose por región/actividad'
        );
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM salario_minimo_vigente
        WHERE region = 'Nacional' AND fecha_inicio = '{FECHA_INICIO}' AND monto_mensual = {MONTO_MENSUAL};
        """
    )

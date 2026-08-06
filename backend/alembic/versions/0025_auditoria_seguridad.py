"""Auditoría y seguridad: multi-tenant + RLS en auditoria_cambios (Fase Auditoría)

La tabla auditoria_cambios existe desde el schema base (migración
0001) pero nunca se tocó en migracion_multiempresa.sql -- a diferencia
de TODAS las demás tablas operativas del proyecto, no tenía
empresa_id ni política RLS. Como esta fase empieza a escribir en ella
activamente (cambios de salario, aprobación de planillas, cálculo y
pago de liquidaciones), se corrige aquí: mismo patrón que
0016/0020/0022 (ENABLE/FORCE ROW LEVEL SECURITY + política de
aislamiento), pero para esta tabla el gap existía desde el diseño
original, no desde una fase reciente.

También se agrega empleado_id (nullable, denormalizado al momento de
escribir cada registro) para poder filtrar "por empleado" sin depender
de joins condicionales según tabla_afectada -- una aprobación de
planilla es un evento de toda la empresa (sin empleado_id), pero un
cambio de salario o una liquidación sí pertenecen a un empleado
concreto.

Revision ID: 0025_auditoria_seguridad
Revises: 0024_liquidaciones_ext
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025_auditoria_seguridad"
down_revision: Union[str, None] = "0024_liquidaciones_ext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE auditoria_cambios ADD COLUMN empresa_id UUID REFERENCES empresas(id);
        ALTER TABLE auditoria_cambios ADD COLUMN empleado_id UUID REFERENCES empleados(id);

        CREATE INDEX idx_auditoria_empleado ON auditoria_cambios(empleado_id);
        CREATE INDEX idx_auditoria_accion ON auditoria_cambios(accion);

        ALTER TABLE auditoria_cambios ENABLE ROW LEVEL SECURITY;
        ALTER TABLE auditoria_cambios FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_auditoria_cambios ON auditoria_cambios
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_auditoria_cambios ON auditoria_cambios;
        ALTER TABLE auditoria_cambios NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE auditoria_cambios DISABLE ROW LEVEL SECURITY;

        DROP INDEX IF EXISTS idx_auditoria_accion;
        DROP INDEX IF EXISTS idx_auditoria_empleado;

        ALTER TABLE auditoria_cambios DROP COLUMN IF EXISTS empleado_id;
        ALTER TABLE auditoria_cambios DROP COLUMN IF EXISTS empresa_id;
        """
    )

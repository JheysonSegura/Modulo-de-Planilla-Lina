"""RLS en movimientos_planilla e historial_salarial (auditoría 2026-08-25, M2)

Hasta ahora estas 2 tablas eran las únicas de las 10 tablas operativas
sin RLS propio (admitido explícitamente en el comentario de
0031_rol_activo_rls_consulta): su aislamiento entre empresas dependía
100% de que cada endpoint nuevo validara primero la planilla/contrato
padre. Ese supuesto ya resultó frágil una vez (ver hallazgo M1,
GET /planillas/{id}/movimientos/{id}/recibo -- el único control real
era un efecto colateral de otra consulta, no un chequeo explícito).

Se agrega empresa_id (denormalizado desde contratos.empresa_id, mismo
valor para ambas tablas vía join) + ENABLE/FORCE ROW LEVEL SECURITY +
política de aislamiento, mismo patrón que provisiones_decimo (0016) y
provisiones_vacaciones (0020). Todo el código que inserta en estas 2
tablas (contratos_service, planilla_service, decimo_service,
migracion_service) ya fue actualizado para poblar empresa_id explícito
en el propio commit de esta migración -- no queda ninguna fila nueva
sin el campo.

Revision ID: 0036_rls_movimientos_historial
Revises: 0035_password_temporal
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036_rls_movimientos_historial"
down_revision: Union[str, None] = "0035_password_temporal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE movimientos_planilla ADD COLUMN empresa_id UUID REFERENCES empresas(id);
        ALTER TABLE historial_salarial ADD COLUMN empresa_id UUID REFERENCES empresas(id);

        UPDATE movimientos_planilla mp
        SET empresa_id = c.empresa_id
        FROM contratos c
        WHERE c.id = mp.contrato_id;

        UPDATE historial_salarial hs
        SET empresa_id = c.empresa_id
        FROM contratos c
        WHERE c.id = hs.contrato_id;

        CREATE INDEX idx_movimientos_planilla_empresa ON movimientos_planilla(empresa_id);
        CREATE INDEX idx_historial_salarial_empresa ON historial_salarial(empresa_id);

        ALTER TABLE movimientos_planilla ENABLE ROW LEVEL SECURITY;
        ALTER TABLE movimientos_planilla FORCE ROW LEVEL SECURITY;
        ALTER TABLE historial_salarial ENABLE ROW LEVEL SECURITY;
        ALTER TABLE historial_salarial FORCE ROW LEVEL SECURITY;

        CREATE POLICY empresa_aislamiento_movimientos_planilla ON movimientos_planilla
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);

        CREATE POLICY empresa_aislamiento_historial_salarial ON historial_salarial
            USING (empresa_id = current_setting('app.empresa_actual')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS empresa_aislamiento_historial_salarial ON historial_salarial;
        DROP POLICY IF EXISTS empresa_aislamiento_movimientos_planilla ON movimientos_planilla;

        ALTER TABLE historial_salarial NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE historial_salarial DISABLE ROW LEVEL SECURITY;
        ALTER TABLE movimientos_planilla NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE movimientos_planilla DISABLE ROW LEVEL SECURITY;

        DROP INDEX IF EXISTS idx_historial_salarial_empresa;
        DROP INDEX IF EXISTS idx_movimientos_planilla_empresa;

        ALTER TABLE historial_salarial DROP COLUMN IF EXISTS empresa_id;
        ALTER TABLE movimientos_planilla DROP COLUMN IF EXISTS empresa_id;
        """
    )

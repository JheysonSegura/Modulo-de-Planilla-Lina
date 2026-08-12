"""RLS: bloquear escritura del rol 'consulta' a nivel de base de datos

Refuerza en Postgres la misma regla que ya aplica require_escritura en
FastAPI (deps.py): el rol 'consulta' es 100% solo lectura, admin y
contador tienen acceso operativo completo. Es defensa en profundidad
-- igual que el aislamiento por empresa (0002_multiempresa_rls,
0006_app_role_rls): si algún día un bug en el backend arma mal un
query o se salta require_escritura, Postgres igual rechaza la
escritura, no solo el código de la ruta.

get_db_rls (app/core/deps.py) ya fija 'app.rol_activo' en la misma
sesión donde fija 'app.empresa_actual', vía set_config con
is_local=true.

Se agregan políticas RESTRICTIVE (se combinan con AND sobre las
políticas permisivas existentes de aislamiento por empresa, nunca las
reemplazan) en las tablas que YA tienen RLS habilitado hoy. Se usa
IS DISTINCT FROM en vez de <> para no romper si la variable de sesión
no está seteada (ej. fixtures de test que insertan directo fijando
solo app.empresa_actual, ver tests/conftest.py::crear_empleado) --
mismo comportamiento laxo que ya asume el resto del proyecto con
app.empresa_actual.

Tablas fuera de alcance (limitación conocida y ya aceptada por el
proyecto, no introducida por esta migración): historial_salarial y
movimientos_planilla no tienen RLS propio (aislamiento transitivo vía
join, ver db/migracion_multiempresa.sql), y empresas/usuarios_empresas
(tablas de gobierno) tampoco -- solo protegidas por require_roles a
nivel de aplicación.

Revision ID: 0031_rol_activo_rls_consulta
Revises: 0030_planillas_constancia_pago
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_rol_activo_rls_consulta"
down_revision: Union[str, None] = "0030_planillas_constancia_pago"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_RLS = [
    "empleados",
    "contratos",
    "planillas",
    "registro_horas_extra",
    "provisiones_vacaciones",
    "ausencias",
    "provisiones_decimo",
    "vacaciones_tomadas",
    "conceptos_variables_pendientes",
    "liquidaciones",
    "auditoria_cambios",
]


def upgrade() -> None:
    tablas = ", ".join(f"'{t}'" for t in _TABLAS_RLS)
    op.execute(
        f"""
        DO $$
        DECLARE
            t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY[{tablas}]
            LOOP
                EXECUTE format(
                    'CREATE POLICY consulta_solo_lectura_insert_%1$I ON %1$I
                        AS RESTRICTIVE FOR INSERT
                        WITH CHECK (current_setting(''app.rol_activo'', true) IS DISTINCT FROM ''consulta'');',
                    t
                );
                EXECUTE format(
                    'CREATE POLICY consulta_solo_lectura_update_%1$I ON %1$I
                        AS RESTRICTIVE FOR UPDATE
                        USING (current_setting(''app.rol_activo'', true) IS DISTINCT FROM ''consulta'')
                        WITH CHECK (current_setting(''app.rol_activo'', true) IS DISTINCT FROM ''consulta'');',
                    t
                );
                EXECUTE format(
                    'CREATE POLICY consulta_solo_lectura_delete_%1$I ON %1$I
                        AS RESTRICTIVE FOR DELETE
                        USING (current_setting(''app.rol_activo'', true) IS DISTINCT FROM ''consulta'');',
                    t
                );
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    tablas = ", ".join(f"'{t}'" for t in _TABLAS_RLS)
    op.execute(
        f"""
        DO $$
        DECLARE
            t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY[{tablas}]
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS consulta_solo_lectura_insert_%1$I ON %1$I;', t);
                EXECUTE format('DROP POLICY IF EXISTS consulta_solo_lectura_update_%1$I ON %1$I;', t);
                EXECUTE format('DROP POLICY IF EXISTS consulta_solo_lectura_delete_%1$I ON %1$I;', t);
            END LOOP;
        END
        $$;
        """
    )

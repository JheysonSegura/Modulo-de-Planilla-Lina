"""Seed de roles base del sistema (admin, contador, consulta)

Roles referenciados como ejemplo en el comentario de la columna
`roles.nombre` de db/schema_nomina_panama.sql. Son datos de referencia
necesarios en todo ambiente (no específicos de desarrollo), ya que
usuarios_empresas.rol_id los requiere.

Revision ID: 0004_seed_roles
Revises: 0003_seed_tasas_legales
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_seed_roles"
down_revision: Union[str, None] = "0003_seed_tasas_legales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO roles (nombre, descripcion) VALUES
            ('admin', 'Acceso total a la empresa: configuración, usuarios y planilla'),
            ('contador', 'Procesa y consulta planilla, sin permisos administrativos'),
            ('consulta', 'Solo lectura');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM roles WHERE nombre IN ('admin', 'contador', 'consulta');
        """
    )

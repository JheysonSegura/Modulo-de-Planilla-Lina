"""Datos personales de empleados: sexo, código país, enfermedad, documentos (Fase 17)

`fecha_nacimiento` y un campo de nacionalidad ya existían en el modelo desde
el schema base pero nunca se expusieron en el frontend; el campo de
nacionalidad estaba mal nombrado como `fecha_nacionalidad` (bug de nombre
heredado). Se renombra a `nacionalidad` ya que esta migración toca toda la
capa de todos modos.

Se agrega `sexo`, se separa el teléfono en `codigo_pais` + `telefono` (antes
solo `telefono` combinado -- los valores existentes no se migran/parsean,
quedan como estaban con `codigo_pais` en blanco), un flag de enfermedad con
detalle opcional, y dos documentos (cédula, certificado médico) como bytea
en la propia tabla -- mismo patrón que `empresas.logo` (0026_empresa_logo):
sin volumen de archivos en docker-compose.yml, servidos aparte por endpoint
dedicado, nunca inline en EmpleadoOut.

Revision ID: 0028_datos_personales_empleados
Revises: 0027_vacaciones_tomadas
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028_datos_personales_empleados"
down_revision: Union[str, None] = "0027_vacaciones_tomadas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE empleados RENAME COLUMN fecha_nacionalidad TO nacionalidad;
        ALTER TABLE empleados ADD COLUMN sexo VARCHAR(20);
        ALTER TABLE empleados ADD COLUMN codigo_pais VARCHAR(5);
        ALTER TABLE empleados ADD COLUMN padece_enfermedad BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE empleados ADD COLUMN detalle_enfermedad TEXT;
        ALTER TABLE empleados ADD COLUMN documento_identificacion BYTEA;
        ALTER TABLE empleados ADD COLUMN documento_identificacion_content_type VARCHAR(50);
        ALTER TABLE empleados ADD COLUMN documento_identificacion_nombre_archivo VARCHAR(255);
        ALTER TABLE empleados ADD COLUMN documento_certificado_medico BYTEA;
        ALTER TABLE empleados ADD COLUMN documento_certificado_medico_content_type VARCHAR(50);
        ALTER TABLE empleados ADD COLUMN documento_certificado_medico_nombre_archivo VARCHAR(255);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_certificado_medico_nombre_archivo;
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_certificado_medico_content_type;
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_certificado_medico;
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_identificacion_nombre_archivo;
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_identificacion_content_type;
        ALTER TABLE empleados DROP COLUMN IF EXISTS documento_identificacion;
        ALTER TABLE empleados DROP COLUMN IF EXISTS detalle_enfermedad;
        ALTER TABLE empleados DROP COLUMN IF EXISTS padece_enfermedad;
        ALTER TABLE empleados DROP COLUMN IF EXISTS codigo_pais;
        ALTER TABLE empleados DROP COLUMN IF EXISTS sexo;
        ALTER TABLE empleados RENAME COLUMN nacionalidad TO fecha_nacionalidad;
        """
    )

"""Seed de tasas_riesgo_profesional (Decreto de Gabinete N.68 de 1970)

FUENTE: Decreto de Gabinete N.68 de 31 de marzo de 1970 ("Por el cual
se centraliza en la Caja de Seguro Social la cobertura obligatoria de
los Riesgos Profesionales"), edición actualizada a abril de 2025 de la
Dirección Ejecutiva Nacional Legal de la CSS, que el usuario agregó al
repo. Los artículos 48-51 (clases/grados de riesgo y fórmula de la
prima) NO aparecen en la lista de "Disposiciones Vinculantes" que
modificaron el decreto original -- siguen vigentes tal como se
decretaron en 1970.

Artículo 49: 5 clases de riesgo, cada una con un rango de "grado de
riesgo" (mínimo/promedio/máximo):
    Clase I   (Riesgo Ordinario de Vida): 6  / 8  / 10
    Clase II  (Riesgo Bajo):               9  / 14 / 19
    Clase III (Riesgo Medio):              17 / 30 / 43
    Clase IV  (Riesgo Alto):               37 / 52 / 67
    Clase V   (Riesgo Máximo):             62 / 81 / 100

Artículo 50, Parágrafo: "Inicialmente las empresas quedarán ubicadas en
el grado promedio de la clase que corresponden" -- se usa el grado
PROMEDIO de cada clase como tasa de referencia sembrada aquí. La CSS
puede asignarle a una empresa específica un grado distinto dentro del
rango de su clase (según su historial de prevención/higiene, vía la
Comisión de Clasificación de Empresas) -- esa asignación específica no
está en este decreto y no se modela aquí; si en el futuro se necesita,
habría que agregar un campo grado_riesgo aparte de clase_riesgo.

Artículo 51: "El monto de las primas... se establecerá multiplicando
el total de salarios por el grado de riesgo... y por un factor
constante igual a siete centésimos (0.07)." Tomado literalmente
(salarios x grado x 0.07) da tasas imposibles para un seguro (ej.
grado 8 x 0.07 = 0.56 = 56% de la planilla). La única lectura que da
tasas plausibles (y consistente con lo que se conoce de las tasas
reales de la CSS por clase de riesgo) es 0.07% POR PUNTO de grado, es
decir tasa = grado x 0.0007:
    Clase I:   8  x 0.0007 = 0.0056 (0.56%)
    Clase II:  14 x 0.0007 = 0.0098 (0.98%)
    Clase III: 30 x 0.0007 = 0.0210 (2.10%)
    Clase IV:  52 x 0.0007 = 0.0364 (3.64%)
    Clase V:   81 x 0.0007 = 0.0567 (5.67%)

DECISIÓN TOMADA CON EL USUARIO (2026-08-05, sin aviso/factura real de
la CSS disponible todavía para verificar la cifra exacta, a diferencia
de ISR con la DGI y décimo con el contador): sembrar estos valores
como MÉTODO interpretado del decreto, marcados explícitamente como NO
confirmados -- mismo tratamiento que tramos_isr antes de la
confirmación de la DGI. Si en una sesión futura el usuario trae un
aviso real de clasificación/factura de la CSS con la tasa exacta de
alguna clase, verificar contra estos valores y corregir vía migración
de datos si no coincide.

empresas.clase_riesgo sigue siendo un campo MANUAL (ya existía desde
el schema base) -- la clase real de cada empresa se la asigna la CSS
según el Reglamento de Clasificación de Empresas que este decreto
delega y que no está en este PDF; el sistema no la infiere de la
actividad económica.

Revision ID: 0019_seed_riesgo_profesional
Revises: 0018_seed_decreto13
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_seed_riesgo_profesional"
down_revision: Union[str, None] = "0018_seed_decreto13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_INICIO = "2025-01-01"

# tasas_riesgo_profesional no tiene columna de fuente/decreto_ref (a
# diferencia de tasas_vigentes) -- la trazabilidad de esta cifra vive
# en el docstring de esta migración, no en la fila misma.
# (clase_riesgo, grado_promedio, tasa = grado_promedio x 0.0007)
CLASES = [
    ("I", 8, "0.0056"),
    ("II", 14, "0.0098"),
    ("III", 30, "0.0210"),
    ("IV", 52, "0.0364"),
    ("V", 81, "0.0567"),
]


def upgrade() -> None:
    valores = ",\n".join(
        f"('{clase}', {tasa}, '{FECHA_INICIO}', NULL)" for clase, _grado, tasa in CLASES
    )
    op.execute(
        f"""
        INSERT INTO tasas_riesgo_profesional (clase_riesgo, tasa, fecha_inicio, fecha_fin)
        VALUES
        {valores};
        """
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM tasas_riesgo_profesional WHERE fecha_inicio = '{FECHA_INICIO}';"
    )

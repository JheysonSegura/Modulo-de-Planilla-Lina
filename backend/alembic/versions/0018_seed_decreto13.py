"""Seed del desglose real de salario mínimo (Decreto Ejecutivo N.13, 31-dic-2025)

Reemplaza la referencia general de $605/mes ('0007_seed_salario_minimo',
siempre marcada como incompleta) por el desglose oficial completo:
Decreto Ejecutivo N.13 de 31 de diciembre de 2025 (Ministerio de
Trabajo y Desarrollo Laboral), publicado en Gaceta Oficial Digital
N.30438 del 6 de enero de 2026, vigente desde el 16 de enero de 2026
(Art. 5) -- deroga el Decreto Ejecutivo N.01 de 10 de enero de 2024.

Transcrito directamente del PDF de la Gaceta que el usuario agregó al
repo (Artículo 2, tabla de tasas por hora según región/actividad
económica/ocupación/tamaño de empresa, más el Artículo 2 Parágrafo para
el trabajador doméstico, que es la única tarifa MENSUAL del decreto).

Reglas de transcripción (ver plan aprobado en la sesión):
  - Actividad marcada "(NACIONAL)" en el decreto -> una sola fila con
    region='Nacional' (tarifa única, no distingue Región 1/2).
  - Actividad con columnas Región 1 / Región 2 -> dos filas.
  - "Zona Libre de Colón" no publica tarifa para Región 2 (guion en el
    decreto) -> solo se inserta la fila de Región 1.
  - División por tamaño de empresa (el umbral de empleados varía por
    sector: 11/15/16) -> mismo `actividad`, dos filas con
    tamano_empresa='Pequeña Empresa' / 'Gran Empresa'. El campo
    tamano_empresa en `empresas` (migración 0017) es una declaración
    manual del admin, no un conteo automático de empleados.
  - División por ocupación específica (ej. conductores de buses,
    talladores de casino) -> el nombre de la ocupación se incorpora al
    propio texto de `actividad`; no hay columna separada para esto.
    LIMITACIÓN CONOCIDA: la resolución en
    app/services/salario_minimo_service.py es a nivel EMPRESA
    (empresas.actividad_economica), no por empleado/contrato -- una
    empresa con roles mixtos (ej. un casino con talladores y cajeros)
    no puede seleccionar automáticamente la fila correcta por
    ocupación todavía. Revisar si algún cliente real lo necesita.

La fila placeholder de 0007 se cierra (fecha_fin) en vez de borrarse:
sigue siendo válida para calcular retroactivamente el 1-15 de enero de
2026, período que este decreto no cubre (empezó a regir el 16).

Revision ID: 0018_seed_decreto13
Revises: 0017_tamano_empresa
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_seed_decreto13"
down_revision: Union[str, None] = "0017_tamano_empresa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FECHA_INICIO = "2026-01-16"
FECHA_CIERRE_PLACEHOLDER = "2026-01-15"
DECRETO_REF = "Decreto Ejecutivo N.13 de 31 de diciembre de 2025"

# (actividad, tamano_empresa, nacional, tarifa_hora_region_1, tarifa_hora_region_2)
# region_2 = None solo en el caso "Zona Libre de Colón" (el decreto no
# publica tarifa para Región 2 ahí). Si nacional=True, la tarifa de
# region_2 se ignora (ambas columnas del decreto ya son iguales).
FILAS_POR_HORA: list[tuple[str, Union[str, None], bool, str, Union[str, None]]] = [
    ("Agricultura, Ganadería, Caza, Silvicultura, Acuicultura, Pesca", "Pequeña Empresa", True, "1.64", None),
    ("Agricultura, Ganadería, Caza, Silvicultura, Acuicultura, Pesca", "Gran Empresa", True, "2.10", None),
    ("Actividades Bananeras", None, True, "2.58", None),
    ("Pesca - Artesanal", None, True, "2.30", None),
    ("Pesca - Industrial", None, True, "2.65", None),
    ("Agroindustrias (parte agrícola)", "Pequeña Empresa", True, "1.67", None),
    ("Agroindustrias (parte agrícola)", "Gran Empresa", True, "2.12", None),
    ("Agroindustrias (parte procesamiento)", "Pequeña Empresa", False, "2.37", "2.00"),
    ("Agroindustrias (parte procesamiento)", "Gran Empresa", False, "3.04", "2.49"),
    ("Explotación de Canteras - Actividades Areneras", None, True, "3.20", None),
    ("Explotación de Canteras - Minas Metálicas", None, True, "3.39", None),
    ("Explotación de Canteras - Minas No Metálicas", None, True, "3.20", None),
    ("Industrias Manufactureras", "Pequeña Empresa", False, "2.32", "1.95"),
    ("Industrias Manufactureras", "Gran Empresa", False, "3.13", "2.58"),
    ("Destilación, Rectificación y mezcla de Bebidas Alcohólicas; Fabricación de Pinturas, Barnices y productos de revestimiento", None, False, "3.08", "2.61"),
    ("Fabricación de Cemento y/o Concreto", None, False, "3.39", "3.24"),
    ("Reparación, Mantenimiento de maquinaria y equipo de refrigeración", None, False, "3.15", "2.57"),
    ("Procesamiento de la Caña de Azúcar", None, True, "3.12", None),
    ("Suministro de Electricidad, Gas, Vapor, Aire Acondicionado", None, True, "3.50", None),
    ("Producción de Hielo", None, False, "3.07", "2.53"),
    ("Suministro de Agua, Alcantarillado, Gestión de Desechos y Actividades de Saneamiento", None, True, "3.50", None),
    ("Alcantarillado", None, False, "3.18", "2.63"),
    ("Recolección, Tratamiento y Eliminación de Desechos", None, False, "3.21", "2.67"),
    ("Procesamiento y Recuperación de Materiales de Desecho", None, False, "3.04", "2.51"),
    ("Construcción", None, False, "3.51", "3.30"),
    ("Drenaje de Tierras Agrícolas y Bosques", None, True, "2.12", None),
    ("Comercio al por Mayor y en Comisiones", None, False, "3.02", "2.48"),
    ("Venta de productos y subproductos derivados de la Caña de Azúcar", None, True, "3.02", None),
    ("Tanques de Combustible", None, False, "3.04", "2.50"),
    ("Comercio al por Menor", "Pequeña Empresa", False, "2.37", "1.99"),
    ("Comercio al por Menor", "Gran Empresa", False, "3.02", "2.48"),
    ("Supermercados (empresas con 5 o más sucursales)", None, False, "3.09", "2.54"),
    ("Estaciones de combustible", None, False, "3.02", "2.48"),
    ("Zonas Francas, Zonas Económicas Especiales", None, False, "3.77", "2.52"),
    ("Zona Libre de Colón", None, False, "3.44", None),
    ("Hoteles", "Pequeña Empresa", False, "2.38", "1.98"),
    ("Hoteles", "Gran Empresa", False, "2.96", "2.43"),
    ("Hoteles y Resorts con Franquicias; Hoteles con más de 200 habitaciones; Hoteles de Ocasión, Moteles, Pensiones y Residenciales", None, False, "3.10", "2.55"),
    ("Restaurantes", "Pequeña Empresa", False, "2.32", "1.95"),
    ("Restaurantes", "Gran Empresa", False, "3.09", "2.54"),
    ("Discotecas, Bares y Cantinas", None, True, "3.40", None),
    ("Transporte", None, False, "3.16", "2.61"),
    ("Transporte de carga en zonas francas o zonas económicas especiales", "Pequeña Empresa", False, "3.47", "2.58"),
    ("Transporte de carga en zonas francas o zonas económicas especiales", "Gran Empresa", False, "3.49", "2.60"),
    ("Transporte por Vía Acuática, Vía Aérea y Actividades Complementarias", "Pequeña Empresa", False, "3.16", "2.58"),
    ("Transporte por Vía Acuática, Vía Aérea y Actividades Complementarias", "Gran Empresa", False, "3.18", "2.60"),
    ("Trabajadores Portuarios", None, True, "3.64", None),
    ("Aeropuertos Internacionales", None, False, "3.84", "3.84"),
    ("Conductores de Buses", None, True, "3.47", None),
    ("Conductores de Buses Colegiales", None, False, "3.02", "2.49"),
    ("Tripulantes de Cabina de Vuelos Internacionales", None, True, "5.01", None),
    ("Almacenamiento, Depósitos y Correos", None, False, "3.02", "2.48"),
    ("Información y Comunicación", None, True, "3.16", None),
    ("Actividades de Edición", None, False, "3.16", "2.62"),
    ("Producción de Programas de Radio y Televisión; Producción de Películas, Videos, Sonidos; Salas de Cine; y Agencias de Noticias", None, False, "3.16", "2.61"),
    ("Telecomunicaciones, Difusión Televisión", None, True, "3.47", None),
    ("Difusión de Radio - Licencia Nacional", None, True, "3.47", None),
    ("Difusión de Radio - Licencia Local", None, True, "3.40", None),
    ("Camarógrafos", None, True, "3.47", None),
    ("Actividades Financieras y de Seguro", None, True, "3.58", None),
    ("Casas de Empeño", None, True, "3.14", None),
    ("Actividades Inmobiliarias", None, False, "3.47", "3.10"),
    ("Centros Comerciales (con más de 50 locales)", None, True, "3.47", None),
    ("Actividades Administrativas y Servicios de Apoyo (Actividades de Alquiler y Arrendamiento)", None, True, "3.12", None),
    ("Renta y Alquiler de Vehículos Automotores", None, True, "3.43", None),
    ("Actividades de Internet Cafés", None, False, "2.82", "2.62"),
    ("Actividades de las Agencias de Empleo", None, True, "3.16", None),
    ("Actividades Agencias de Viajes, Operadores Turísticos y Servicios de Reserva", None, False, "3.09", "2.44"),
    ("Actividades de Servicio a Edificios y Paisajes", None, True, "2.98", None),
    ("Actividades de Servicio de Mantenimiento y Cuidado de Paisajes (Jardines, Áreas Verdes)", None, True, "2.12", None),
    ("Actividades de Oficinas Administrativas, Soporte de Negocios; Fotocopiados", None, True, "2.98", None),
    ("Actividades de Seguridad e Investigación (Agencias de Seguridad y Vigilancia)", None, True, "3.04", None),
    ("Actividades Profesionales, Científicas y Técnicas", None, True, "3.02", None),
    ("Actividades Veterinarias", None, False, "3.02", "2.48"),
    ("Firmas de Abogados, Contabilidad y Auditoría", "Gran Empresa", True, "3.18", None),
    ("Firmas de Abogados, Contabilidad y Auditoría", "Pequeña Empresa", True, "2.89", None),
    ("Abogados", None, True, "3.70", None),
    ("Periodistas de Radio, Periódicos y Televisión", None, True, "3.45", None),
    ("Mecánicos de Transporte Aéreo", None, True, "4.92", None),
    ("Mecánicos de Transporte Terrestre", None, True, "3.45", None),
    ("Mecánicos de Transporte Marítimo", None, True, "3.83", None),
    ("Enseñanza (Personal Administrativo)", None, False, "3.09", "2.52"),
    ("Servicios Sociales y Relacionados con la Salud Humana", None, False, "3.22", "2.64"),
    ("Clínicas de Salud y Hospitales", None, False, "3.54", "2.66"),
    ("Técnicos de Salud", None, True, "3.54", None),
    ("Artes, Entretenimiento y Creatividad", None, True, "3.11", None),
    ("Actividades de Juegos de Azar y Apuestas", None, True, "3.63", None),
    ("Casinos - Talladores, Gerente de Casino, Jefes de Sala, Operadores de CCTV", None, True, "3.72", None),
    ("Casinos - Seguridad, Aseadores, Saloneros, Oficinistas, Cajeros, etc.", None, True, "3.61", None),
    ("Gimnasios", None, True, "3.43", None),
    ("Otras Actividades de Servicios", None, False, "3.12", "2.55"),
    ("Organizaciones Sin Fines de Lucro", None, False, "2.98", "2.45"),
    ("Reparación y Mantenimiento de Computadoras", None, True, "2.96", None),
    ("Reparación y Mantenimiento de Enseres de uso Personal y Domésticos", "Pequeña Empresa", False, "2.32", "1.94"),
    ("Reparación y Mantenimiento de Enseres de uso Personal y Domésticos", "Gran Empresa", False, "2.98", "2.52"),
    ("Propiedades Horizontales Residenciales (que sumen más de 10 plantas) y Asociaciones de Inquilinos de Viviendas Individuales", None, True, "3.43", None),
    ("Spas, Clínicas Estéticas", None, False, "3.43", "2.57"),
    ("Actividades de Organizaciones y Órganos Extraterritoriales", None, True, "3.16", None),
]

# (actividad, region, monto_mensual) -- único caso mensual del decreto.
FILAS_MENSUALES: list[tuple[str, str, str]] = [
    ("Trabajador Doméstico", "Región 1", "350.00"),
    ("Trabajador Doméstico", "Región 2", "320.00"),
]


def _escapar(valor: str) -> str:
    return valor.replace("'", "''")


def _construir_filas() -> list[tuple[str, str, Union[str, None], Union[str, None], Union[str, None]]]:
    """Devuelve tuplas (region, actividad, tamano_empresa, monto_hora, monto_mensual)."""
    filas: list[tuple[str, str, Union[str, None], Union[str, None], Union[str, None]]] = []
    for actividad, tamano, nacional, r1, r2 in FILAS_POR_HORA:
        if nacional:
            filas.append(("Nacional", actividad, tamano, r1, None))
        else:
            filas.append(("Región 1", actividad, tamano, r1, None))
            if r2 is not None:
                filas.append(("Región 2", actividad, tamano, r2, None))
    for actividad, region, monto_mensual in FILAS_MENSUALES:
        filas.append((region, actividad, None, None, monto_mensual))
    return filas


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE salario_minimo_vigente
        SET fecha_fin = '{FECHA_CIERRE_PLACEHOLDER}'
        WHERE region = 'Nacional' AND actividad IS NULL
          AND fecha_inicio = '2026-01-01' AND monto_mensual = 605.00
          AND fecha_fin IS NULL;
        """
    )

    valores = []
    for region, actividad, tamano, monto_hora, monto_mensual in _construir_filas():
        tamano_sql = f"'{_escapar(tamano)}'" if tamano is not None else "NULL"
        monto_hora_sql = monto_hora if monto_hora is not None else "NULL"
        monto_mensual_sql = monto_mensual if monto_mensual is not None else "NULL"
        valores.append(
            f"('{region}', '{_escapar(actividad)}', {tamano_sql}, {monto_hora_sql}, "
            f"{monto_mensual_sql}, '{FECHA_INICIO}', NULL, '{DECRETO_REF}')"
        )

    columnas = "region, actividad, tamano_empresa, monto_hora, monto_mensual, fecha_inicio, fecha_fin, decreto_ref"
    op.execute(
        f"INSERT INTO salario_minimo_vigente ({columnas}) VALUES\n" + ",\n".join(valores) + ";"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM salario_minimo_vigente WHERE decreto_ref = '{DECRETO_REF}';")
    op.execute(
        f"""
        UPDATE salario_minimo_vigente
        SET fecha_fin = NULL
        WHERE region = 'Nacional' AND actividad IS NULL
          AND fecha_inicio = '2026-01-01' AND monto_mensual = 605.00
          AND fecha_fin = '{FECHA_CIERRE_PLACEHOLDER}';
        """
    )

import datetime
import decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Empresa, SalarioMinimoVigente
from app.repositories import salario_minimo as salario_minimo_repo

# Jornada de referencia de tiempo completo (el default de
# contratos.jornada_horas_semana). Un contrato de medio tiempo se
# prorratea sobre esta base, no se compara contra el mínimo mensual
# completo.
JORNADA_TIEMPO_COMPLETO = decimal.Decimal("48")

# Equivalente mensual de una tarifa por hora (Decreto Ejecutivo N.13):
# mismo mes comercial de 30 días y jornada de 8h ya usado en todo el
# proyecto para salario_diario (Art. 54 CT), aplicado al revés.
HORAS_JORNADA_DIARIA = decimal.Decimal("8")
DIAS_MES_COMERCIAL = decimal.Decimal("30")


def validar_salario_minimo(
    db: Session,
    empresa: Empresa,
    fecha: datetime.date,
    salario_mensual: decimal.Decimal,
    jornada_horas_semana: decimal.Decimal = JORNADA_TIEMPO_COMPLETO,
) -> None:
    """Valida contra el salario mínimo vigente EN LA FECHA DEL CONTRATO
    (no el actual): un contrato retroactivo se valida contra lo que regía
    en ese momento, según fecha_inicio/fecha_fin de salario_minimo_vigente.

    Medio tiempo: se prorratea el mínimo por jornada_horas_semana, nunca
    se exige el mínimo mensual completo a alguien contratado por menos
    horas. Pasantías u otros casos con tratamiento legal no confirmado
    se manejan aparte con contratos.exento_salario_minimo (ver
    contratos_service, que ni siquiera llama a esta función si el
    contrato está marcado como exento).

    Cuando hay más de un salario mínimo vigente a la vez (multi-región/
    actividad/tamaño de empresa, Decreto Ejecutivo N.13), se elige la
    fila según empresa.region / empresa.actividad_economica /
    empresa.tamano_empresa; si no hay forma segura de elegir, se
    rechaza en vez de adivinar.

    La mayoría de las filas del decreto son tarifa POR HORA, no
    mensual (excepto Trabajador Doméstico): se convierten a mensual
    con `monto_hora × 8 × 30` antes de comparar.
    """
    filas = salario_minimo_repo.listar_vigente_en_fecha(db, fecha)
    if not filas:
        return  # nada sembrado para esa fecha; no hay nada contra qué validar

    fila = _elegir_fila_aplicable(
        filas, empresa.region, empresa.actividad_economica, empresa.tamano_empresa
    )
    if fila is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Hay más de un salario mínimo vigente para el {fecha.isoformat()} y ninguno "
            "calza sin ambigüedad con la región/actividad económica/tamaño de empresa "
            "configurados. Define empresa.region, empresa.actividad_economica y/o "
            "empresa.tamano_empresa (PATCH /empresas/actual) para poder resolverlo.",
        )

    monto_base_mensual = fila.monto_mensual
    if monto_base_mensual is None and fila.monto_hora is not None:
        monto_base_mensual = fila.monto_hora * HORAS_JORNADA_DIARIA * DIAS_MES_COMERCIAL
    if monto_base_mensual is None:
        return

    factor = min(jornada_horas_semana / JORNADA_TIEMPO_COMPLETO, decimal.Decimal("1"))
    minimo_aplicable = (monto_base_mensual * factor).quantize(decimal.Decimal("0.01"))

    if salario_mensual < minimo_aplicable:
        nota_prorrateo = (
            f" (prorrateado a {jornada_horas_semana}h/semana sobre ${monto_base_mensual} de base)"
            if factor < 1
            else ""
        )
        nota_fuente = f" ({fila.decreto_ref})" if fila.decreto_ref else ""
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El salario ${salario_mensual} está por debajo del salario mínimo vigente "
            f"(${minimo_aplicable}{nota_prorrateo}) para el {fecha.isoformat()}{nota_fuente}.",
        )


def _elegir_fila_aplicable(
    filas: list[SalarioMinimoVigente],
    region: str | None,
    actividad: str | None,
    tamano_empresa: str | None,
) -> SalarioMinimoVigente | None:
    if len(filas) == 1:
        return filas[0]

    # 1) Coincidencia por actividad: dentro de esas, resolver por región
    # (exacta o el piso "Nacional") y luego por tamaño de empresa.
    if actividad is not None:
        candidatas = [fila for fila in filas if fila.actividad == actividad]
        if candidatas:
            return _resolver_por_region_y_tamano(candidatas, region, tamano_empresa)

    # 2) Sin actividad (o sin match): fila general de la región, sin actividad.
    if region is not None:
        generales = [fila for fila in filas if fila.actividad is None and fila.region == region]
        if len(generales) == 1:
            return generales[0]

    # 3) Piso "Nacional" sin actividad, si hay exactamente uno.
    nacionales = [fila for fila in filas if fila.region == "Nacional" and fila.actividad is None]
    if len(nacionales) == 1:
        return nacionales[0]

    return None  # ambiguo: no hay forma segura de elegir automáticamente


def _resolver_por_region_y_tamano(
    candidatas: list[SalarioMinimoVigente],
    region: str | None,
    tamano_empresa: str | None,
) -> SalarioMinimoVigente | None:
    # Preferir región exacta sobre el piso "Nacional" cuando hay ambas.
    exactas = [fila for fila in candidatas if fila.region == region]
    pool = exactas if exactas else [fila for fila in candidatas if fila.region == "Nacional"]
    if not pool:
        pool = candidatas
    if len(pool) == 1:
        return pool[0]

    if tamano_empresa is not None:
        con_tamano = [fila for fila in pool if fila.tamano_empresa == tamano_empresa]
        if len(con_tamano) == 1:
            return con_tamano[0]

    sin_tamano = [fila for fila in pool if fila.tamano_empresa is None]
    if len(sin_tamano) == 1:
        return sin_tamano[0]

    return None  # ambiguo: p.ej. la actividad se divide por tamaño y la empresa no lo declaró

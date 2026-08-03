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
    actividad, Decreto Ejecutivo N.13), se elige la fila según
    empresa.region / empresa.actividad_economica; si no hay forma segura
    de elegir, se rechaza en vez de adivinar.
    """
    filas = salario_minimo_repo.listar_vigente_en_fecha(db, fecha)
    if not filas:
        return  # nada sembrado para esa fecha; no hay nada contra qué validar

    fila = _elegir_fila_aplicable(filas, empresa.region, empresa.actividad_economica)
    if fila is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Hay más de un salario mínimo vigente para el {fecha.isoformat()} y ninguno "
            "calza con la región/actividad económica configurada en la empresa. Define "
            "empresa.region y empresa.actividad_economica (PATCH /empresas/actual) para "
            "poder resolverlo.",
        )

    if fila.monto_mensual is None:
        return

    factor = min(jornada_horas_semana / JORNADA_TIEMPO_COMPLETO, decimal.Decimal("1"))
    minimo_aplicable = (fila.monto_mensual * factor).quantize(decimal.Decimal("0.01"))

    if salario_mensual < minimo_aplicable:
        nota_prorrateo = (
            f" (prorrateado a {jornada_horas_semana}h/semana sobre ${fila.monto_mensual} de base)"
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
) -> SalarioMinimoVigente | None:
    if len(filas) == 1:
        return filas[0]

    # 1) Coincidencia exacta región + actividad.
    if region is not None and actividad is not None:
        for fila in filas:
            if fila.region == region and fila.actividad == actividad:
                return fila

    # 2) Misma región, fila general para toda la región (sin actividad).
    if region is not None:
        for fila in filas:
            if fila.region == region and fila.actividad is None:
                return fila

    # 3) Piso "Nacional" que sirve de respaldo, si hay exactamente uno.
    nacionales = [fila for fila in filas if fila.region == "Nacional"]
    if len(nacionales) == 1:
        return nacionales[0]

    return None  # ambiguo: no hay forma segura de elegir automáticamente

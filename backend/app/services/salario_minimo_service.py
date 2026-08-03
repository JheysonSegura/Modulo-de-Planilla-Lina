import datetime
import decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import salario_minimo as salario_minimo_repo


def validar_salario_minimo(db: Session, fecha: datetime.date, salario_mensual: decimal.Decimal) -> None:
    """Valida contra el salario mínimo vigente EN LA FECHA DEL CONTRATO
    (no el actual): un contrato retroactivo se valida contra lo que regía
    en ese momento, según fecha_inicio/fecha_fin de salario_minimo_vigente.

    CLAUDE.md señala que el salario mínimo puede variar por región/
    actividad y que salario_minimo_vigente todavía no tiene datos reales
    cargados (pendiente de las cifras oficiales del Decreto 13). Mientras
    no haya filas para una fecha, no hay nada contra qué validar y se deja
    pasar; si algún día hay más de una región vigente a la vez, hace falta
    decidir cómo un contrato/empresa se vincula a una región antes de
    poder elegir automáticamente cuál aplica, así que se rechaza en vez de
    adivinar.
    """
    filas = salario_minimo_repo.listar_vigente_en_fecha(db, fecha)
    if not filas:
        return

    if len(filas) > 1:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Hay más de un salario mínimo vigente para esta fecha (multi-región) y "
            "todavía no existe un vínculo empresa/contrato -> región para elegir cuál "
            "aplica automáticamente. Hay que definir esa regla antes de continuar.",
        )

    minimo = filas[0]
    if minimo.monto_mensual is not None and salario_mensual < minimo.monto_mensual:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El salario ${salario_mensual} está por debajo del salario mínimo vigente "
            f"(${minimo.monto_mensual}) para el {fecha.isoformat()}"
            f"{f' ({minimo.decreto_ref})' if minimo.decreto_ref else ''}.",
        )

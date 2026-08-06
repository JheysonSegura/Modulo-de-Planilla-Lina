import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    SalarioMinimoVigente,
    TasaRiesgoProfesional,
    TasaVigente,
    TramoIsr,
)


def _vigente_en(fecha: datetime.date, columna_inicio, columna_fin):
    return (columna_inicio <= fecha) & (or_(columna_fin.is_(None), columna_fin >= fecha))


def obtener_tasa_vigente(
    db: Session, tipo_tasa: str, fecha: datetime.date
) -> TasaVigente | None:
    stmt = select(TasaVigente).where(
        TasaVigente.tipo_tasa == tipo_tasa,
        TasaVigente.fecha_inicio <= fecha,
        or_(TasaVigente.fecha_fin.is_(None), TasaVigente.fecha_fin >= fecha),
    )
    return db.scalar(stmt)


def obtener_tasa_riesgo_profesional_vigente(
    db: Session, clase_riesgo: str, fecha: datetime.date
) -> TasaRiesgoProfesional | None:
    """Devuelve None si la empresa no tiene clase_riesgo asignada o si
    no hay tasa sembrada para esa clase en la fecha dada; quien llama
    debe tratar None como riesgo_profesional_patronal=0, no como un
    error (ver CLAUDE.md sección 4: la tasa por clase I-V está
    sembrada como interpretación del Decreto de Gabinete N.68/1970,
    NO confirmada todavía por un aviso real de la CSS)."""
    stmt = select(TasaRiesgoProfesional).where(
        TasaRiesgoProfesional.clase_riesgo == clase_riesgo,
        TasaRiesgoProfesional.fecha_inicio <= fecha,
        or_(
            TasaRiesgoProfesional.fecha_fin.is_(None),
            TasaRiesgoProfesional.fecha_fin >= fecha,
        ),
    )
    return db.scalar(stmt)


def listar_vigentes(
    db: Session, fecha: datetime.date, tipo_tasa: str | None = None
) -> list[TasaVigente]:
    stmt = select(TasaVigente).where(_vigente_en(fecha, TasaVigente.fecha_inicio, TasaVigente.fecha_fin))
    if tipo_tasa is not None:
        stmt = stmt.where(TasaVigente.tipo_tasa == tipo_tasa)
    stmt = stmt.order_by(TasaVigente.tipo_tasa)
    return list(db.execute(stmt).scalars().all())


def listar_tramos_isr(db: Session, fecha: datetime.date) -> list[TramoIsr]:
    stmt = (
        select(TramoIsr)
        .where(_vigente_en(fecha, TramoIsr.fecha_inicio, TramoIsr.fecha_fin))
        .order_by(TramoIsr.monto_desde)
    )
    return list(db.execute(stmt).scalars().all())


def listar_riesgo_profesional(db: Session, fecha: datetime.date) -> list[TasaRiesgoProfesional]:
    stmt = (
        select(TasaRiesgoProfesional)
        .where(_vigente_en(fecha, TasaRiesgoProfesional.fecha_inicio, TasaRiesgoProfesional.fecha_fin))
        .order_by(TasaRiesgoProfesional.clase_riesgo)
    )
    return list(db.execute(stmt).scalars().all())


def listar_salario_minimo(
    db: Session,
    fecha: datetime.date,
    region: str | None = None,
    actividad: str | None = None,
) -> list[SalarioMinimoVigente]:
    stmt = select(SalarioMinimoVigente).where(
        _vigente_en(fecha, SalarioMinimoVigente.fecha_inicio, SalarioMinimoVigente.fecha_fin)
    )
    if region is not None:
        stmt = stmt.where(SalarioMinimoVigente.region == region)
    if actividad is not None:
        stmt = stmt.where(SalarioMinimoVigente.actividad.ilike(f"%{actividad}%"))
    stmt = stmt.order_by(SalarioMinimoVigente.region, SalarioMinimoVigente.actividad)
    return list(db.execute(stmt).scalars().all())

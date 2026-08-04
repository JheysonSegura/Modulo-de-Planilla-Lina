import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import TasaRiesgoProfesional, TasaVigente


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
    """tasas_riesgo_profesional no tiene ningún dato sembrado todavía
    (pendiente de la tabla oficial de la CSS por clase I-V, ver
    CLAUDE.md secciones 4/6): esto devuelve None hasta que se siembre,
    y quien llama debe tratar None como riesgo_profesional_patronal=0,
    no como un error."""
    stmt = select(TasaRiesgoProfesional).where(
        TasaRiesgoProfesional.clase_riesgo == clase_riesgo,
        TasaRiesgoProfesional.fecha_inicio <= fecha,
        or_(
            TasaRiesgoProfesional.fecha_fin.is_(None),
            TasaRiesgoProfesional.fecha_fin >= fecha,
        ),
    )
    return db.scalar(stmt)

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

import datetime

from sqlalchemy.orm import Session

from app.models import SalarioMinimoVigente, TasaRiesgoProfesional, TasaVigente, TramoIsr
from app.repositories import tasas as tasas_repo


def listar_vigentes(
    db: Session, tipo_tasa: str | None = None, fecha: datetime.date | None = None
) -> list[TasaVigente]:
    return tasas_repo.listar_vigentes(db, fecha or datetime.date.today(), tipo_tasa)


def listar_tramos_isr(db: Session, fecha: datetime.date | None = None) -> list[TramoIsr]:
    return tasas_repo.listar_tramos_isr(db, fecha or datetime.date.today())


def listar_riesgo_profesional(
    db: Session, fecha: datetime.date | None = None
) -> list[TasaRiesgoProfesional]:
    return tasas_repo.listar_riesgo_profesional(db, fecha or datetime.date.today())


def listar_salario_minimo(
    db: Session,
    region: str | None = None,
    actividad: str | None = None,
    fecha: datetime.date | None = None,
) -> list[SalarioMinimoVigente]:
    return tasas_repo.listar_salario_minimo(db, fecha or datetime.date.today(), region, actividad)

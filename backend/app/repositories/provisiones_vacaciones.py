import datetime
import decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProvisionVacaciones


def get_abierta(db: Session, contrato_id: uuid.UUID) -> ProvisionVacaciones | None:
    """El período de vacaciones "actual" del contrato: el que todavía
    no se cerró. Debe haber como máximo uno por contrato (no se modela
    la acumulación de hasta 2 períodos del Art. 59 CT todavía)."""
    stmt = select(ProvisionVacaciones).where(
        ProvisionVacaciones.contrato_id == contrato_id,
        ProvisionVacaciones.estado == "abierto",
    )
    return db.scalar(stmt)


def crear(
    db: Session,
    empresa_id: uuid.UUID,
    contrato_id: uuid.UUID,
    fecha_inicio_periodo: datetime.date,
) -> ProvisionVacaciones:
    provision = ProvisionVacaciones(
        empresa_id=empresa_id,
        contrato_id=contrato_id,
        fecha_inicio_periodo=fecha_inicio_periodo,
    )
    db.add(provision)
    db.flush()
    return provision


def actualizar(
    db: Session,
    provision: ProvisionVacaciones,
    dias_acumulados: decimal.Decimal,
    monto_provisionado: decimal.Decimal,
) -> ProvisionVacaciones:
    """Recalcula completo cada vez (igual que provisiones_decimo): una
    planilla generada fuera de orden no descuadra la provisión."""
    provision.dias_acumulados = dias_acumulados
    provision.monto_provisionado = monto_provisionado
    db.flush()
    return provision


def registrar_goce(
    db: Session,
    provision: ProvisionVacaciones,
    dias_acumulados: decimal.Decimal,
    dias_gozados: decimal.Decimal,
    monto_provisionado: decimal.Decimal,
) -> ProvisionVacaciones:
    provision.dias_acumulados = dias_acumulados
    provision.dias_gozados = dias_gozados
    provision.monto_provisionado = monto_provisionado
    db.flush()
    return provision


def listar_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[ProvisionVacaciones]:
    stmt = (
        select(ProvisionVacaciones)
        .where(ProvisionVacaciones.contrato_id == contrato_id)
        .order_by(ProvisionVacaciones.fecha_inicio_periodo)
    )
    return list(db.execute(stmt).scalars().all())

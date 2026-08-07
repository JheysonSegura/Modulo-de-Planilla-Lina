import datetime
import decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProvisionVacaciones, VacacionTomada


def get_abierta(db: Session, contrato_id: uuid.UUID) -> ProvisionVacaciones | None:
    """El período de vacaciones "actual" del contrato, el que sigue
    acumulando saldo nuevo. Debe haber como máximo uno por contrato en
    estado 'abierto' (el segundo período, si existe por acumulación
    del Art. 59 CT, queda en estado 'acumulado' -- ver get_todas_activas)."""
    stmt = select(ProvisionVacaciones).where(
        ProvisionVacaciones.contrato_id == contrato_id,
        ProvisionVacaciones.estado == "abierto",
    )
    return db.scalar(stmt)


def get_acumulada(db: Session, contrato_id: uuid.UUID) -> ProvisionVacaciones | None:
    """El período que quedó "congelado" tras una acumulación (Fase 12,
    Art. 59 CT). Debe haber como máximo uno por contrato -- la ley
    limita la acumulación a 2 períodos en total."""
    stmt = select(ProvisionVacaciones).where(
        ProvisionVacaciones.contrato_id == contrato_id,
        ProvisionVacaciones.estado == "acumulado",
    )
    return db.scalar(stmt)


def get_todas_activas(db: Session, contrato_id: uuid.UUID) -> list[ProvisionVacaciones]:
    """Los períodos 'abierto'/'acumulado' del contrato (0-2 filas),
    ordenados por fecha_inicio_periodo (el más antiguo primero, para
    consumo FIFO del saldo -- ver vacaciones_service.registrar_vacacion_tomada)."""
    stmt = (
        select(ProvisionVacaciones)
        .where(
            ProvisionVacaciones.contrato_id == contrato_id,
            ProvisionVacaciones.estado.in_(("abierto", "acumulado")),
        )
        .order_by(ProvisionVacaciones.fecha_inicio_periodo)
    )
    return list(db.execute(stmt).scalars().all())


def marcar_acumulado(
    db: Session, provision: ProvisionVacaciones, notificado_autoridad_trabajo: bool
) -> ProvisionVacaciones:
    provision.estado = "acumulado"
    provision.notificado_autoridad_trabajo = notificado_autoridad_trabajo
    db.flush()
    return provision


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


def crear_evento_tomado(
    db: Session,
    empresa_id: uuid.UUID,
    provision: ProvisionVacaciones,
    contrato_id: uuid.UUID,
    fecha: datetime.date,
    dias_tomados: decimal.Decimal,
    valor_dia: decimal.Decimal,
    monto: decimal.Decimal,
    dias_acumulados_snapshot: decimal.Decimal,
    dias_gozados_snapshot: decimal.Decimal,
) -> VacacionTomada:
    """Fase 16: un registro por cada período efectivamente tocado dentro
    de una llamada a vacaciones_service.registrar_vacacion_tomada -- ver
    ese servicio para el detalle de por qué puede haber más de una fila
    por llamada (toma que cruza el período 'acumulado' y el 'abierto')."""
    evento = VacacionTomada(
        empresa_id=empresa_id,
        provision_id=provision.id,
        contrato_id=contrato_id,
        fecha=fecha,
        dias_tomados=dias_tomados,
        valor_dia=valor_dia,
        monto=monto,
        dias_acumulados_snapshot=dias_acumulados_snapshot,
        dias_gozados_snapshot=dias_gozados_snapshot,
    )
    db.add(evento)
    db.flush()
    return evento


def listar_eventos_de_contrato(db: Session, contrato_id: uuid.UUID) -> list[VacacionTomada]:
    stmt = (
        select(VacacionTomada)
        .where(VacacionTomada.contrato_id == contrato_id)
        .order_by(VacacionTomada.fecha.desc(), VacacionTomada.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def obtener_evento(db: Session, evento_id: uuid.UUID) -> VacacionTomada | None:
    return db.get(VacacionTomada, evento_id)

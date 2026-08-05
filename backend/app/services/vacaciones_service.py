import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, ProvisionVacaciones
from app.repositories import historial_salarial as historial_repo
from app.repositories import provisiones_vacaciones as provisiones_vacaciones_repo

# Código de Trabajo, Art. 54.1: "Treinta días por cada once meses
# continuos de trabajo, a razón de un día por cada once días al
# servicio de su empleador." Verificado contra código-detrabajo.pdf el
# 2026-08-05 -- coincide exacto con lo ya documentado en CLAUDE.md, sin
# discrepancias con la fuente primaria (a diferencia del décimo en
# Fase 8, donde el decreto original sí difería en dos puntos).
DIAS_MES_COMERCIAL = decimal.Decimal("30")
DIVISOR_VACACIONES = decimal.Decimal("11")
_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")


def _calcular_dias_y_monto_acumulado(
    db: Session,
    contrato: Contrato,
    fecha_inicio_periodo: datetime.date,
    fecha_corte: datetime.date,
) -> tuple[decimal.Decimal, decimal.Decimal]:
    """días_acumulados = (días trabajados / 11); monto = misma suma
    valorizada al salario_diario de cada segmento. Recorre cada
    segmento de historial_salarial que se solapa con el rango (mismo
    patrón que decimo_service._calcular... / calcular_decimo_de_contrato,
    Fase 8) para que un cambio de salario a mitad del período se calcule
    con precisión, no con un promedio.

    "Días trabajados" se simplifica a días calendario en que el
    contrato estuvo activo -- no hay tabla de ausencias/licencias en
    este proyecto todavía. El Art. 54.4 CT cuenta también como días
    trabajados los descansos semanales, días de fiesta/duelo nacional y
    licencias por enfermedad dentro de límites -- limitación conocida,
    igual que en el décimo (Fase 8)."""
    if fecha_corte < fecha_inicio_periodo:
        return _CERO, _CERO

    segmentos = historial_repo.listar_de_contrato(db, contrato.id)
    dias_totales = _CERO
    monto_total = _CERO
    for segmento in segmentos:
        seg_fin = segmento.fecha_vigencia_hasta or fecha_corte
        efectivo_inicio = max(
            segmento.fecha_vigencia_desde, fecha_inicio_periodo, contrato.fecha_inicio
        )
        efectivo_fin = min(seg_fin, fecha_corte, contrato.fecha_fin_real or fecha_corte)
        if efectivo_fin < efectivo_inicio:
            continue
        dias_calendario = decimal.Decimal((efectivo_fin - efectivo_inicio).days + 1)
        salario_diario = segmento.salario_base / DIAS_MES_COMERCIAL
        dias_totales += dias_calendario / DIVISOR_VACACIONES
        monto_total += (dias_calendario / DIVISOR_VACACIONES) * salario_diario

    return dias_totales.quantize(_CENTAVO), monto_total.quantize(_CENTAVO)


def _valor_dia_actual(db: Session, contrato: Contrato, fecha: datetime.date) -> decimal.Decimal:
    """Valor del día usado para descontar días ya gozados: el salario
    vigente a la fecha del goce (Art. 54.2 CT: "el último salario base,
    según resulte más favorable"), no el histórico de cuando se acumuló
    cada día."""
    segmento = historial_repo.get_vigente_en_fecha(db, contrato.id, fecha)
    if segmento is None:
        segmento = historial_repo.get_abierto(db, contrato.id)
    if segmento is None:
        return _CERO
    return segmento.salario_base / DIAS_MES_COMERCIAL


def _obtener_o_crear_provision_abierta(
    db: Session, empresa_id: uuid.UUID, contrato: Contrato
) -> ProvisionVacaciones:
    provision = provisiones_vacaciones_repo.get_abierta(db, contrato.id)
    if provision is None:
        provision = provisiones_vacaciones_repo.crear(
            db, empresa_id, contrato.id, contrato.fecha_inicio
        )
    return provision


def actualizar_provision(
    db: Session, empresa_id: uuid.UUID, contrato: Contrato, fecha_corte: datetime.date
) -> ProvisionVacaciones:
    """Se llama desde planilla_service.generar_planilla al procesar
    cada contrato, igual que decimo_service.actualizar_provision:
    recalcula completo el acumulado desde el inicio del período abierto
    del contrato hasta fecha_corte (nunca incrementalmente), así una
    planilla generada fuera de orden no descuadra la provisión."""
    provision = _obtener_o_crear_provision_abierta(db, empresa_id, contrato)

    dias_acumulados, monto_bruto = _calcular_dias_y_monto_acumulado(
        db, contrato, provision.fecha_inicio_periodo, fecha_corte
    )
    valor_dia = _valor_dia_actual(db, contrato, fecha_corte)
    monto_provisionado = monto_bruto - (provision.dias_gozados * valor_dia)
    if monto_provisionado < _CERO:
        monto_provisionado = _CERO

    return provisiones_vacaciones_repo.actualizar(
        db, provision, dias_acumulados, monto_provisionado.quantize(_CENTAVO)
    )


def listar_provisiones(db: Session, contrato_id: uuid.UUID) -> list[ProvisionVacaciones]:
    return provisiones_vacaciones_repo.listar_de_contrato(db, contrato_id)


def registrar_vacacion_tomada(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    dias_tomados: decimal.Decimal,
    fecha: datetime.date,
) -> ProvisionVacaciones:
    """Registra días de vacación efectivamente gozados, descontándolos
    del saldo disponible. Recalcula el acumulado fresco a `fecha` antes
    de validar el saldo (mismo criterio que
    decimo_service.generar_pago_decimo: "recalcula fresco... para que
    quede sincronizado por construcción antes de aplicar el cambio")."""
    if dias_tomados <= _CERO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "dias_tomados debe ser mayor que cero."
        )

    provision = _obtener_o_crear_provision_abierta(db, empresa_id, contrato)

    dias_acumulados, monto_bruto = _calcular_dias_y_monto_acumulado(
        db, contrato, provision.fecha_inicio_periodo, fecha
    )
    saldo_disponible = dias_acumulados - provision.dias_gozados
    if dias_tomados > saldo_disponible:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Solo hay {saldo_disponible} días de vacaciones disponibles al "
            f"{fecha.isoformat()}, se intentaron tomar {dias_tomados}.",
        )

    nuevos_dias_gozados = provision.dias_gozados + dias_tomados
    valor_dia = _valor_dia_actual(db, contrato, fecha)
    monto_provisionado = monto_bruto - (nuevos_dias_gozados * valor_dia)
    if monto_provisionado < _CERO:
        monto_provisionado = _CERO

    provision = provisiones_vacaciones_repo.registrar_goce(
        db, provision, dias_acumulados, nuevos_dias_gozados, monto_provisionado.quantize(_CENTAVO)
    )
    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5/6/8 (SET
    # LOCAL app.empresa_actual no sobrevive al commit).
    return provision

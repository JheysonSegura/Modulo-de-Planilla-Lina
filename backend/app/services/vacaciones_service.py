import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, ProvisionVacaciones
from app.repositories import historial_salarial as historial_repo
from app.repositories import provisiones_vacaciones as provisiones_vacaciones_repo
from app.services import ausencias_service

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

    "Días trabajados" resta los días de ausencias que no cuentan según
    ausencias_service (Fase 11, Art. 199/200/208 CT -- incluye la
    regla de "solo se descuenta el exceso sobre 15 días" y las
    excepciones de embarazo/riesgo profesional/huelga legal, que nunca
    se descuentan)."""
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
        dias_calendario -= ausencias_service.dias_no_contables(
            db, contrato.id, efectivo_inicio, efectivo_fin
        )
        if dias_calendario < _CERO:
            dias_calendario = _CERO
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
    del saldo disponible. Si el contrato acumuló un segundo período
    (Fase 12, Art. 59 CT), consume primero el período 'acumulado' (el
    más antiguo) y luego el 'abierto' (FIFO, mismo criterio que
    horas_extra_service para topes) -- ver get_todas_activas.

    El período 'abierto' se recalcula fresco a `fecha` antes de validar
    el saldo (mismo criterio que decimo_service.generar_pago_decimo).
    El período 'acumulado' NO se recalcula: quedó "congelado" en
    dias_acumulados desde que se acumuló (acumular_periodo), así que
    aquí solo se le resta el valor de los días tomados al
    monto_provisionado que ya tenía -- a diferencia del 'abierto', que
    siempre se recalcula completo desde cero."""
    if dias_tomados <= _CERO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "dias_tomados debe ser mayor que cero."
        )

    periodos = provisiones_vacaciones_repo.get_todas_activas(db, contrato.id)
    if not periodos:
        periodos = [_obtener_o_crear_provision_abierta(db, empresa_id, contrato)]

    valor_dia = _valor_dia_actual(db, contrato, fecha)

    calculos = []
    saldo_total = _CERO
    for periodo in periodos:
        if periodo.estado == "abierto":
            dias_acumulados, monto_bruto = _calcular_dias_y_monto_acumulado(
                db, contrato, periodo.fecha_inicio_periodo, fecha
            )
        else:  # 'acumulado': congelado, no se recalcula desde historial_salarial
            dias_acumulados, monto_bruto = periodo.dias_acumulados, None
        saldo = dias_acumulados - periodo.dias_gozados
        calculos.append((periodo, saldo, dias_acumulados, monto_bruto))
        saldo_total += saldo

    if dias_tomados > saldo_total:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Solo hay {saldo_total} días de vacaciones disponibles al "
            f"{fecha.isoformat()}, se intentaron tomar {dias_tomados}.",
        )

    restante = dias_tomados
    ultimo_modificado: ProvisionVacaciones | None = None
    for periodo, saldo, dias_acumulados, monto_bruto in calculos:
        if restante <= _CERO:
            break
        tomar = min(restante, saldo)
        if tomar <= _CERO:
            continue

        nuevos_dias_gozados = periodo.dias_gozados + tomar
        if periodo.estado == "abierto":
            monto_provisionado = monto_bruto - (nuevos_dias_gozados * valor_dia)
        else:
            monto_provisionado = periodo.monto_provisionado - (tomar * valor_dia)
        if monto_provisionado < _CERO:
            monto_provisionado = _CERO

        ultimo_modificado = provisiones_vacaciones_repo.registrar_goce(
            db, periodo, dias_acumulados, nuevos_dias_gozados, monto_provisionado.quantize(_CENTAVO)
        )
        restante -= tomar

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5/6/8 (SET
    # LOCAL app.empresa_actual no sobrevive al commit).
    assert ultimo_modificado is not None  # dias_tomados > 0 y <= saldo_total: siempre toca algo
    return ultimo_modificado


def acumular_periodo(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    fecha_acuerdo: datetime.date,
    notificado_autoridad_trabajo: bool,
) -> ProvisionVacaciones:
    """Acumula el período de vacaciones 'abierto' actual (Fase 12,
    Art. 59 CT: "las vacaciones serán acumulables hasta por dos
    períodos, mediante acuerdo entre el empleador y el trabajador que
    será notificado a la autoridad de trabajo"). NO es automático por
    el solo paso del tiempo -- requiere este acuerdo explícito. El
    sistema no tramita la notificación real (proceso administrativo
    externo); `notificado_autoridad_trabajo` es informativo.

    Congela el período actual (pasa a estado 'acumulado', deja de
    crecer) y abre uno nuevo desde el día siguiente al acuerdo. Exige
    al menos 15 días de saldo sin gozar en el período actual (Art. 59:
    "el trabajador tendrá un descanso mínimo de quince días
    remunerados en el primer período")."""
    periodo_abierto = provisiones_vacaciones_repo.get_abierta(db, contrato.id)
    if periodo_abierto is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No hay un período de vacaciones abierto para acumular."
        )
    if provisiones_vacaciones_repo.get_acumulada(db, contrato.id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este contrato ya tiene un período acumulado -- el Art. 59 CT permite "
            "acumular hasta por 2 períodos en total.",
        )

    dias_acumulados, monto_bruto = _calcular_dias_y_monto_acumulado(
        db, contrato, periodo_abierto.fecha_inicio_periodo, fecha_acuerdo
    )
    saldo = dias_acumulados - periodo_abierto.dias_gozados
    if saldo < decimal.Decimal("15"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Saldo insuficiente para acumular: el Art. 59 CT exige al menos 15 días sin "
            f"gozar en el período actual, hay {saldo} disponibles al {fecha_acuerdo.isoformat()}.",
        )

    valor_dia = _valor_dia_actual(db, contrato, fecha_acuerdo)
    monto_provisionado = monto_bruto - (periodo_abierto.dias_gozados * valor_dia)
    if monto_provisionado < _CERO:
        monto_provisionado = _CERO

    periodo_abierto = provisiones_vacaciones_repo.actualizar(
        db, periodo_abierto, dias_acumulados, monto_provisionado.quantize(_CENTAVO)
    )
    provisiones_vacaciones_repo.marcar_acumulado(db, periodo_abierto, notificado_autoridad_trabajo)

    nuevo_periodo = provisiones_vacaciones_repo.crear(
        db, empresa_id, contrato.id, fecha_acuerdo + datetime.timedelta(days=1)
    )
    db.commit()
    # Sin db.refresh(): rompería RLS igual que el resto de este archivo.
    return nuevo_periodo

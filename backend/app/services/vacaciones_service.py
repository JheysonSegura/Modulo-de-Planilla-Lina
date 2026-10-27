import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Contrato,
    MovimientoPlanilla,
    Planilla,
    ProvisionVacaciones,
    VacacionTomada,
)
from app.repositories import empresas as empresas_repo
from app.repositories import historial_salarial as historial_repo
from app.repositories import movimientos_planilla as movimientos_repo
from app.repositories import planillas as planillas_repo
from app.repositories import provisiones_vacaciones as provisiones_vacaciones_repo
from app.repositories import tasas as tasas_repo
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


def listar_eventos_tomados(db: Session, contrato_id: uuid.UUID) -> list[VacacionTomada]:
    return provisiones_vacaciones_repo.listar_eventos_de_contrato(db, contrato_id)


def obtener_evento_tomado(
    db: Session, contrato_id: uuid.UUID, evento_id: uuid.UUID
) -> VacacionTomada:
    """Fase 16: usado por el endpoint de recibo de vacaciones. RLS ya
    filtra por empresa; acá solo se valida que el evento pertenezca al
    contrato de la URL."""
    evento = provisiones_vacaciones_repo.obtener_evento(db, evento_id)
    if evento is None or evento.contrato_id != contrato_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento de vacaciones no encontrado")
    return evento


def registrar_vacacion_tomada(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    dias_tomados: decimal.Decimal,
    fecha: datetime.date,
    fecha_pago: datetime.date | None = None,
    usuario_id: uuid.UUID | None = None,
) -> ProvisionVacaciones:
    """Registra días de vacación efectivamente gozados, descontándolos
    del saldo disponible. `dias_tomados` llega siempre como entero desde
    el schema (VacacionTomadaCreate.dias: int, 2026-08-07) -- un
    trabajador toma días de calendario completos, nunca una fracción de
    día, a diferencia de dias_acumulados (Art. 54.1 CT, decimal por
    diseño). Si el contrato acumuló un segundo período (Fase 12, Art. 59
    CT), consume primero el período 'acumulado' (el más antiguo) y luego
    el 'abierto' (FIFO, mismo criterio que horas_extra_service para
    topes) -- ver get_todas_activas.

    Limitación conocida, no resuelta acá: si una toma entera cruza los
    dos períodos y el saldo del primero no es también entero (ej.
    acumulado con saldo 15.27 y se piden 20 días), el reparto por período
    en `vacaciones_tomadas` puede mostrar una fila fraccionaria para ese
    evento puntual (15.27 + 4.73), aunque el total tomado sí sea entero
    -- la fracción ahí refleja fielmente cuánto quedaba en ese balde
    legado, no es un error de cálculo. No se resolvió por ser un caso de
    borde de Fase 12 (ya confirmada) fuera del alcance pedido el
    2026-08-07 (que era sobre el caso simple de un solo período).

    El período 'abierto' se recalcula fresco a `fecha` antes de validar
    el saldo (mismo criterio que decimo_service.generar_pago_decimo).
    El período 'acumulado' NO se recalcula: quedó "congelado" en
    dias_acumulados desde que se acumuló (acumular_periodo), así que
    aquí solo se le resta el valor de los días tomados al
    monto_provisionado que ya tenía -- a diferencia del 'abierto', que
    siempre se recalcula completo desde cero.

    Descuentos de ley (2026-10-23, ver PLAN-vacaciones-descuentos.md):
    `fecha` es el inicio del descanso, que dura `dias_tomados` días
    calendario. Cada toma genera su propia Planilla tipo='vacaciones'
    (borrador -> aprobar -> pagar, igual que el décimo) con un
    MovimientoPlanilla que lleva CSS/SE/riesgo profesional (mismas tasas
    que una quincena, a `fecha_pago`) e ISR = impuesto anual proyectado
    ÷ 12 × días/30. Ese pago REEMPLAZA el salario de esos días en las
    quincenas (planilla_service._calcular_movimiento_de_contrato), así que
    se rechaza la toma si ya hay una planilla regular o de vacaciones no
    anulada que cubra alguno de esos días -- habría doble pago.
    `fecha_pago` por defecto es 3 días antes del descanso (Art. 54.5 CT)."""
    if dias_tomados <= _CERO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "dias_tomados debe ser mayor que cero."
        )
    fecha_fin_goce = fecha + datetime.timedelta(days=int(dias_tomados) - 1)
    if fecha_pago is None:
        fecha_pago = fecha - datetime.timedelta(days=3)

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

    solapada = movimientos_repo.buscar_planilla_que_solapa(
        db, contrato.id, ("mensual", "quincenal", "vacaciones"), fecha, fecha_fin_goce
    )
    if solapada is not None:
        if solapada.tipo == "vacaciones":
            detalle = "Ya hay vacaciones registradas que cubren parte de esos días"
        else:
            detalle = (
                f"Ya hay una planilla {solapada.tipo} (estado '{solapada.estado}') que paga el "
                "salario de parte de esos días"
            )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{detalle} ({solapada.periodo_inicio.isoformat()} a "
            f"{solapada.periodo_fin.isoformat()}). El descanso va del {fecha.isoformat()} al "
            f"{fecha_fin_goce.isoformat()}; para no pagar dos veces los mismos días, anula "
            "primero esa planilla si todavía está en borrador, o elige otra fecha de inicio.",
        )

    planilla, movimiento = _crear_planilla_de_vacaciones(
        db, empresa_id, usuario_id, contrato, dias_tomados, valor_dia, fecha, fecha_fin_goce,
        fecha_pago,
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
        # Fase 16: un registro de historial por cada período efectivamente
        # tocado, para poder emitir un recibo por esta toma concreta -- ver
        # crear_evento_tomado. Antes del commit final, mismo patrón que
        # registrar_goce (db.flush() adentro, sin refresh tras el commit).
        provisiones_vacaciones_repo.crear_evento_tomado(
            db,
            empresa_id,
            ultimo_modificado,
            contrato.id,
            fecha,
            fecha_fin_goce,
            tomar,
            valor_dia,
            (tomar * valor_dia).quantize(_CENTAVO),
            dias_acumulados,
            nuevos_dias_gozados,
            movimiento.id,
        )
        restante -= tomar

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5/6/8 (SET
    # LOCAL app.empresa_actual no sobrevive al commit).
    assert ultimo_modificado is not None  # dias_tomados > 0 y <= saldo_total: siempre toca algo
    return ultimo_modificado


def _crear_planilla_de_vacaciones(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID | None,
    contrato: Contrato,
    dias_tomados: decimal.Decimal,
    valor_dia: decimal.Decimal,
    fecha: datetime.date,
    fecha_fin_goce: datetime.date,
    fecha_pago: datetime.date,
) -> tuple[Planilla, MovimientoPlanilla]:
    """Planilla tipo='vacaciones' en borrador con un solo movimiento, mismo
    patrón que decimo_service.generar_pago_decimo. El pago de vacaciones es
    salario: lleva las mismas cuotas que una quincena (CSS, Seguro
    Educativo, riesgo profesional), con las tasas vigentes a `fecha_pago`.
    El ISR es el del mes que reemplaza: impuesto anual proyectado ÷ 12 ×
    días/30 (decisión del usuario 2026-10-23), y la reconciliación anual
    de las quincenas siguientes ajusta cualquier diferencia."""
    # Import local: planilla_service ya importa este módulo (anular una
    # planilla de vacaciones llama a revertir_toma_de_planilla).
    from app.services import planilla_service

    empresa = empresas_repo.get(db, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    salario_bruto = (dias_tomados * valor_dia).quantize(_CENTAVO)

    def _cuota(tipo_tasa: str) -> decimal.Decimal:
        factor = planilla_service._factor_obligatorio(db, tipo_tasa, fecha_pago)
        return (salario_bruto * factor).quantize(_CENTAVO)

    css_empleado = _cuota("css_empleado")
    css_patronal = _cuota("css_patronal")
    seguro_educativo_empleado = _cuota("seguro_educativo_empleado")
    seguro_educativo_patronal = _cuota("seguro_educativo_patronal")

    riesgo_profesional_patronal = _CERO
    if empresa.clase_riesgo:
        tasa_riesgo = tasas_repo.obtener_tasa_riesgo_profesional_vigente(
            db, empresa.clase_riesgo, fecha_pago
        )
        if tasa_riesgo is not None:
            riesgo_profesional_patronal = (salario_bruto * tasa_riesgo.tasa).quantize(_CENTAVO)

    salario_mensual = valor_dia * DIAS_MES_COMERCIAL
    impuesto_anual, renta_bruta_anual, decimo_tratamiento = (
        planilla_service.calcular_impuesto_anual_proyectado(db, salario_mensual, fecha)
    )
    isr_retenido = (
        impuesto_anual / decimal.Decimal("12") * dias_tomados / DIAS_MES_COMERCIAL
    ).quantize(_CENTAVO)

    planilla = Planilla(
        empresa_id=empresa_id,
        tipo="vacaciones",
        periodo_inicio=fecha,
        periodo_fin=fecha_fin_goce,
        fecha_pago=fecha_pago,
        estado="borrador",
        procesada_por=usuario_id,
    )
    planillas_repo.crear(db, planilla)

    movimiento = MovimientoPlanilla(
        empresa_id=empresa_id,
        planilla_id=planilla.id,
        contrato_id=contrato.id,
        salario_base_periodo=salario_bruto,
        salario_bruto=salario_bruto,
        css_empleado=css_empleado,
        css_patronal=css_patronal,
        seguro_educativo_empleado=seguro_educativo_empleado,
        seguro_educativo_patronal=seguro_educativo_patronal,
        riesgo_profesional_patronal=riesgo_profesional_patronal,
        isr_retenido=isr_retenido,
        isr_renta_anual_proyectada=renta_bruta_anual,
        isr_impuesto_anual_proyectado=impuesto_anual,
        isr_decimo_tratamiento=decimo_tratamiento,
        otras_deducciones=_CERO,
        salario_neto=salario_bruto - css_empleado - seguro_educativo_empleado - isr_retenido,
    )
    movimientos_repo.crear(db, movimiento)
    return planilla, movimiento


def revertir_toma_de_planilla(db: Session, planilla: Planilla) -> None:
    """Se llama desde planilla_service.anular_planilla cuando se anula una
    planilla tipo='vacaciones' (solo en borrador): devuelve los días de
    cada fila de la toma a su período de vacaciones y las marca anuladas.
    No hace commit -- lo hace anular_planilla junto con el cambio de
    estado y la auditoría.

    Rechaza si una planilla regular no anulada ya descontó esos días
    (planilla_service los resta como "pagados aparte"): anular solo la de
    vacaciones dejaría esos días sin pagar en ningún lado."""
    movimientos = movimientos_repo.listar_de_planilla(db, planilla.id)
    hasta = planilla.periodo_fin
    if hasta.day == 30 and (hasta + datetime.timedelta(days=1)).day == 31:
        # Regresó el día 31: el período que arranca el 1 del mes siguiente
        # ya le pagó ese día (planilla_service.dia_31_trabajado_tras_vacaciones).
        # Sin la vacación, la quincena 16-31 lo volvería a pagar.
        hasta += datetime.timedelta(days=2)
    for movimiento in movimientos:
        regular = movimientos_repo.buscar_planilla_que_solapa(
            db,
            movimiento.contrato_id,
            ("mensual", "quincenal"),
            planilla.periodo_inicio,
            hasta,
        )
        if regular is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"La planilla {regular.tipo} del {regular.periodo_inicio.isoformat()} al "
                f"{regular.periodo_fin.isoformat()} (estado '{regular.estado}') ya descontó "
                "estos días de vacaciones del salario. Anúlala primero (si sigue en borrador) "
                "para no dejar esos días sin pagar.",
            )

    for movimiento in movimientos:
        for evento in provisiones_vacaciones_repo.listar_eventos_de_movimiento(db, movimiento.id):
            if evento.anulada:
                continue
            provision = provisiones_vacaciones_repo.get(db, evento.provision_id)
            # El 'abierto' igual se recalcula completo en la próxima
            # planilla; el 'acumulado' está congelado y solo así recupera
            # el valor de esos días.
            provisiones_vacaciones_repo.registrar_goce(
                db,
                provision,
                provision.dias_acumulados,
                max(provision.dias_gozados - evento.dias_tomados, _CERO),
                provision.monto_provisionado + evento.monto,
            )
            evento.anulada = True
    db.flush()


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

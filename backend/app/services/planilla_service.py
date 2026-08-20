import calendar
import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    ConceptoVariable,
    ConceptoVariablePendiente,
    Contrato,
    Empresa,
    MovimientoPlanilla,
    Planilla,
)
from app.repositories import conceptos_variables as conceptos_variables_repo
from app.repositories import conceptos_variables_pendientes as pendientes_repo
from app.repositories import contratos as contratos_repo
from app.repositories import empresas as empresas_repo
from app.repositories import historial_salarial as historial_repo
from app.repositories import horas_extra as horas_extra_repo
from app.repositories import movimientos_planilla as movimientos_repo
from app.repositories import parametros_isr as parametros_isr_repo
from app.repositories import planillas as planillas_repo
from app.repositories import tasas as tasas_repo
from app.repositories import tramos_isr as tramos_isr_repo
from app.services import ausencias_service, auditoria_service, decimo_service, vacaciones_service

# Períodos de pago por año según el tipo de planilla (no
# contratos.periodicidad_pago -- el motor de Fase 6 es genérico por
# rango de fechas, y el ISR sigue el mismo criterio).
PERIODOS_POR_ANIO = {"mensual": 12, "quincenal": 24}

# Mes comercial de 30 días (Art. 54 CT, CLAUDE.md sección 5): cualquier
# prorrateo usa salario_mensual/30, nunca los días calendario reales.
DIAS_MES_COMERCIAL = decimal.Decimal("30")

# Días "comerciales" que cubre un período completo según su tipo. Un
# período quincenal completo son exactamente 15 de esos 30 días,
# nunca los días calendario reales del rango (una segunda quincena de
# un mes de 31 días sigue pagando la mitad del mes, no 16/30).
TIPO_A_DIAS_COMERCIALES = {"mensual": decimal.Decimal("30"), "quincenal": decimal.Decimal("15")}

_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")


def generar_planilla(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    tipo: str,
    periodo_inicio: datetime.date,
    periodo_fin: datetime.date,
    fecha_pago: datetime.date,
) -> Planilla:
    existente = planillas_repo.buscar_por_periodo(db, empresa_id, tipo, periodo_inicio, periodo_fin)
    if existente is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya existe una planilla '{tipo}' para el período {periodo_inicio.isoformat()} a "
            f"{periodo_fin.isoformat()} (id={existente.id}, estado={existente.estado}). "
            "Anúlala primero si necesitas regenerarla.",
        )

    empresa = empresas_repo.get(db, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    planilla = Planilla(
        empresa_id=empresa_id,
        tipo=tipo,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        fecha_pago=fecha_pago,
        estado="borrador",
        procesada_por=usuario_id,
    )
    planillas_repo.crear(db, planilla)

    contratos = contratos_repo.listar_vigentes_en_periodo(db, empresa_id, periodo_inicio, periodo_fin)
    for contrato in contratos:
        movimiento, conceptos, pendientes_aplicados = _calcular_movimiento_de_contrato(
            db, empresa, contrato, tipo, periodo_inicio, periodo_fin
        )
        movimiento.planilla_id = planilla.id
        movimientos_repo.crear(db, movimiento)

        for concepto in conceptos:
            concepto.movimiento_planilla_id = movimiento.id
            conceptos_variables_repo.crear(db, concepto)

        for pendiente in pendientes_aplicados:
            pendiente.aplicado = True
            pendiente.movimiento_planilla_id = movimiento.id

        # Fase 8: cada planilla regular actualiza (recalcula completo)
        # la provisión de décimo del cuatrimestre que contiene su
        # periodo_fin, para que el pasivo acumulado esté al día sin
        # pasos manuales adicionales.
        decimo_service.actualizar_provision(db, empresa_id, contrato, periodo_fin)

        # Fase 9: mismo criterio -- recalcula completo el acumulado de
        # vacaciones (1 día por cada 11 trabajados, Art. 54 CT) del
        # período abierto del contrato hasta periodo_fin.
        vacaciones_service.actualizar_provision(db, empresa_id, contrato, periodo_fin)

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5 (SET LOCAL
    # app.empresa_actual no sobrevive al commit). planilla ya tiene sus
    # campos poblados en Python desde antes del commit.
    return planilla


def listar_planillas(
    db: Session, empresa_id: uuid.UUID, tipo: str | None = None, estado: str | None = None
) -> list[Planilla]:
    return planillas_repo.listar(db, empresa_id, tipo, estado)


def obtener_planilla(db: Session, planilla_id: uuid.UUID) -> Planilla:
    planilla = planillas_repo.get(db, planilla_id)
    if planilla is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planilla no encontrada")
    return planilla


def listar_movimientos(db: Session, planilla_id: uuid.UUID) -> list[MovimientoPlanilla]:
    return movimientos_repo.listar_de_planilla(db, planilla_id)


def obtener_movimiento(
    db: Session, planilla_id: uuid.UUID, movimiento_id: uuid.UUID
) -> MovimientoPlanilla:
    """Fase 16: usado por el endpoint de recibo de pago. RLS ya filtra
    por empresa; acá solo se valida que el movimiento pertenezca a la
    planilla de la URL (evita recibos cruzados entre planillas)."""
    movimiento = movimientos_repo.get(db, movimiento_id)
    if movimiento is None or movimiento.planilla_id != planilla_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimiento no encontrado")
    return movimiento


def aprobar_planilla(
    db: Session, empresa_id: uuid.UUID, usuario_id: uuid.UUID, planilla: Planilla
) -> Planilla:
    """Transición borrador -> procesada (vocabulario del schema
    original, `db/schema_nomina_panama.sql`: 'borrador','procesada',
    'pagada','anulada' -- nunca implementada hasta esta fase). Cambio
    mínimo: solo el estado + el registro de auditoría, sin bloquear ni
    recalcular los movimientos ya generados."""
    if planilla.estado != "borrador":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La planilla ya está en estado '{planilla.estado}', no se puede aprobar de nuevo.",
        )

    estado_anterior = planilla.estado
    planilla.estado = "procesada"

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "planillas",
        planilla.id,
        "aprobada",
        datos_anteriores={"estado": estado_anterior},
        datos_nuevos={"estado": planilla.estado},
    )

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto.
    return planilla


def pagar_planilla(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    planilla: Planilla,
    contenido: bytes,
    content_type: str,
    nombre_archivo: str,
) -> Planilla:
    """Transición procesada -> pagada (vocabulario reservado desde el
    schema original, nunca implementado hasta ahora). A diferencia de
    liquidaciones_service.pagar_liquidacion, esta transición exige
    subir la constancia bancaria del pago -- el router valida que
    `archivo` esté presente y tenga un content-type soportado antes de
    llegar acá; este servicio solo persiste el documento junto con el
    cambio de estado."""
    if planilla.estado != "procesada":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La planilla está en estado '{planilla.estado}'; solo se puede confirmar el pago de "
            "una planilla aprobada (procesada).",
        )

    estado_anterior = planilla.estado
    planilla.estado = "pagada"
    planilla.documento_constancia_pago = contenido
    planilla.documento_constancia_pago_content_type = content_type
    planilla.documento_constancia_pago_nombre_archivo = nombre_archivo

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "planillas",
        planilla.id,
        "pagada",
        datos_anteriores={"estado": estado_anterior},
        datos_nuevos={"estado": planilla.estado},
    )

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto.
    return planilla


def reemplazar_constancia_pago(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    planilla: Planilla,
    contenido: bytes,
    content_type: str,
    nombre_archivo: str,
    motivo: str,
) -> Planilla:
    """Reemplaza la constancia de una planilla ya pagada (ej. se subió el
    archivo equivocado por error). No toca `estado` -- la planilla se
    queda en 'pagada', solo cambia el documento. Restringido a admin
    desde el router; exige `motivo` para dejar rastro auditado de POR
    QUÉ se corrigió un comprobante de pago, no solo que se corrigió."""
    if planilla.estado != "pagada":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La planilla está en estado '{planilla.estado}'; solo se puede reemplazar la "
            "constancia de una planilla ya pagada. Para pagarla por primera vez usá "
            "'Confirmar pago'.",
        )

    nombre_anterior = planilla.documento_constancia_pago_nombre_archivo
    planilla.documento_constancia_pago = contenido
    planilla.documento_constancia_pago_content_type = content_type
    planilla.documento_constancia_pago_nombre_archivo = nombre_archivo

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "planillas",
        planilla.id,
        "constancia_repuesta",
        datos_anteriores={"archivo": nombre_anterior},
        datos_nuevos={"archivo": nombre_archivo, "motivo": motivo},
    )

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto.
    return planilla


def anular_planilla(
    db: Session, empresa_id: uuid.UUID, usuario_id: uuid.UUID, planilla: Planilla
) -> Planilla:
    """Transición borrador -> anulada (vocabulario reservado desde el
    schema original, nunca implementado hasta ahora). Es la vía correcta
    para descartar una planilla que no se va a usar (ej. faltaba un
    empleado por ingresar) -- nunca un borrado físico: las provisiones de
    décimo/vacaciones se recalculan completas en cada planilla real, así
    que no quedan desincronizadas, pero los conceptos variables pendientes
    (bonos, comisiones, descuentos puntuales) que esta planilla marcó como
    aplicados sí quedarían perdidos para siempre si no se revierten."""
    if planilla.estado != "borrador":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La planilla está en estado '{planilla.estado}'; solo se puede anular una planilla "
            "en borrador.",
        )

    estado_anterior = planilla.estado
    planilla.estado = "anulada"
    pendientes_repo.revertir_aplicados_de_planilla(db, planilla.id)

    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "planillas",
        planilla.id,
        "anulada",
        datos_anteriores={"estado": estado_anterior},
        datos_nuevos={"estado": planilla.estado},
    )

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto.
    return planilla


def _calcular_movimiento_de_contrato(
    db: Session,
    empresa: Empresa,
    contrato: Contrato,
    tipo: str,
    periodo_inicio: datetime.date,
    periodo_fin: datetime.date,
) -> tuple[MovimientoPlanilla, list[ConceptoVariable], list[ConceptoVariablePendiente]]:
    salario_vigente = historial_repo.get_vigente_en_fecha(db, contrato.id, periodo_fin)
    if salario_vigente is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay un salario registrado para el contrato {contrato.id} en la fecha "
            f"{periodo_fin.isoformat()} (fin del período de esta planilla).",
        )
    salario_mensual = salario_vigente.salario_base
    salario_diario = salario_mensual / DIAS_MES_COMERCIAL

    cubre_periodo_completo = contrato.fecha_inicio <= periodo_inicio and (
        contrato.fecha_fin_real is None or contrato.fecha_fin_real >= periodo_fin
    )
    if cubre_periodo_completo:
        efectivo_inicio = periodo_inicio
        efectivo_fin = periodo_fin
        if tipo == "mensual":
            salario_base_periodo = salario_mensual
        else:
            salario_base_periodo = (salario_mensual / decimal.Decimal("2")).quantize(_CENTAVO)
    else:
        efectivo_inicio = max(contrato.fecha_inicio, periodo_inicio)
        efectivo_fin = min(contrato.fecha_fin_real or periodo_fin, periodo_fin)
        dias_trabajados = (efectivo_fin - efectivo_inicio).days + 1
        salario_base_periodo = (salario_diario * decimal.Decimal(dias_trabajados)).quantize(_CENTAVO)

    conceptos: list[ConceptoVariable] = []

    dias_sin_goce = ausencias_service.dias_sin_goce_de_salario(
        db, contrato.id, efectivo_inicio, efectivo_fin
    )
    monto_descuento_ausencia = (dias_sin_goce * salario_diario).quantize(_CENTAVO)
    if monto_descuento_ausencia > _CERO:
        salario_base_periodo -= monto_descuento_ausencia
        conceptos.append(
            ConceptoVariable(
                tipo="informativo",
                codigo="ausencia_sin_goce",
                descripcion=(
                    f"{dias_sin_goce} día(s) de ausencia injustificada sin goce de salario "
                    f"({periodo_inicio.isoformat()} a {periodo_fin.isoformat()})"
                ),
                monto=-monto_descuento_ausencia,
            )
        )

    registros_horas_extra = horas_extra_repo.listar_de_contrato(
        db, contrato.id, periodo_inicio, periodo_fin
    )
    monto_horas_extra = sum((r.monto_calculado for r in registros_horas_extra), _CERO)
    if monto_horas_extra > _CERO:
        conceptos.append(
            ConceptoVariable(
                tipo="ingreso",
                codigo="hora_extra",
                descripcion=f"Horas extra {periodo_inicio.isoformat()} a {periodo_fin.isoformat()}",
                monto=monto_horas_extra,
            )
        )

    pendientes = pendientes_repo.listar_pendientes_de_contrato(
        db, contrato.id, periodo_inicio, periodo_fin
    )
    monto_variables_ingreso = _CERO
    monto_variables_deduccion = _CERO
    for pendiente in pendientes:
        conceptos.append(
            ConceptoVariable(
                tipo=pendiente.tipo,
                codigo=pendiente.codigo,
                descripcion=pendiente.descripcion,
                monto=pendiente.monto,
            )
        )
        if pendiente.tipo == "ingreso":
            monto_variables_ingreso += pendiente.monto
        else:
            monto_variables_deduccion += pendiente.monto

    # Base gravable de CSS/SE = todo ingreso remunerativo del período
    # (fijo + variable); los 'deduccion' bajan el neto, no la base.
    salario_bruto = salario_base_periodo + monto_horas_extra + monto_variables_ingreso
    otras_deducciones = monto_variables_deduccion
    base_gravable = salario_bruto

    css_empleado = (base_gravable * _factor_obligatorio(db, "css_empleado", periodo_fin)).quantize(
        _CENTAVO
    )
    css_patronal = (base_gravable * _factor_obligatorio(db, "css_patronal", periodo_fin)).quantize(
        _CENTAVO
    )
    seguro_educativo_empleado = (
        base_gravable * _factor_obligatorio(db, "seguro_educativo_empleado", periodo_fin)
    ).quantize(_CENTAVO)
    seguro_educativo_patronal = (
        base_gravable * _factor_obligatorio(db, "seguro_educativo_patronal", periodo_fin)
    ).quantize(_CENTAVO)

    riesgo_profesional_patronal = _CERO
    if empresa.clase_riesgo:
        tasa_riesgo = tasas_repo.obtener_tasa_riesgo_profesional_vigente(
            db, empresa.clase_riesgo, periodo_fin
        )
        # None es un estado normal (empresa sin clase_riesgo asignada
        # por la CSS, o sin tasa vigente para esa clase en la fecha),
        # no un error -- ver CLAUDE.md sección 4.
        if tasa_riesgo is not None:
            riesgo_profesional_patronal = (base_gravable * tasa_riesgo.tasa).quantize(_CENTAVO)

    isr_retenido, isr_auditoria = _calcular_isr_retenido(
        db, contrato, tipo, periodo_inicio, periodo_fin, salario_mensual
    )

    salario_neto = (
        salario_bruto - css_empleado - seguro_educativo_empleado - isr_retenido - otras_deducciones
    )

    movimiento = MovimientoPlanilla(
        contrato_id=contrato.id,
        salario_base_periodo=salario_base_periodo,
        salario_bruto=salario_bruto,
        css_empleado=css_empleado,
        css_patronal=css_patronal,
        seguro_educativo_empleado=seguro_educativo_empleado,
        seguro_educativo_patronal=seguro_educativo_patronal,
        riesgo_profesional_patronal=riesgo_profesional_patronal,
        isr_retenido=isr_retenido,
        isr_renta_anual_proyectada=isr_auditoria["isr_renta_anual_proyectada"],
        isr_impuesto_anual_proyectado=isr_auditoria["isr_impuesto_anual_proyectado"],
        isr_decimo_tratamiento=isr_auditoria["isr_decimo_tratamiento"],
        isr_numero_periodo_anio=isr_auditoria["isr_numero_periodo_anio"],
        isr_periodos_restantes_anio=isr_auditoria["isr_periodos_restantes_anio"],
        otras_deducciones=otras_deducciones,
        salario_neto=salario_neto,
    )
    return movimiento, conceptos, pendientes


def _factor_obligatorio(db: Session, tipo_tasa: str, fecha: datetime.date) -> decimal.Decimal:
    tasa = tasas_repo.obtener_tasa_vigente(db, tipo_tasa, fecha)
    if tasa is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay una tasa vigente para '{tipo_tasa}' en la fecha {fecha.isoformat()}. "
            "Verifica el seed de tasas_vigentes.",
        )
    return tasa.tasa


def _calcular_isr_retenido(
    db: Session,
    contrato: Contrato,
    tipo: str,
    periodo_inicio: datetime.date,
    periodo_fin: datetime.date,
    salario_mensual_vigente: decimal.Decimal,
) -> tuple[decimal.Decimal, dict]:
    """ISR por el método CONFIRMADO por el contador el 2026-08-04 (caso
    numérico verificado: $2,500/mes -> $32,500 bruto anual con décimo
    -> $21,500 excedente sobre $11,000 -> 15% -> $3,225.00/año ->
    $268.75/mes -- ver CLAUDE.md sección 5 y FASE7-plan-isr.txt):
    (1) proyectar renta bruta anual = salario_mensual × 13 (12 meses +
    décimo, ver más abajo), (2) restar el tramo exento y aplicar la
    tasa marginal sobre el excedente -- **sin restar CSS/SE de la
    base, a diferencia de lo que documentaba originalmente CLAUDE.md**
    sección 6 antes de esta confirmación --, (3) prorratear el
    impuesto anual entre los períodos de pago restantes, reconciliando
    contra lo ya retenido este año (ajuste progresivo).

    Las cifras exactas de tramos_isr siguen sin validación formal del
    contador; el método sí está confirmado. Solo se anualiza el
    salario fijo recurrente -- horas extra y conceptos variables del
    período no se proyectan a 12 meses, no hay garantía de que se
    repitan.

    Corrección 2026-08-18 (confirmada por el contador, encontrada por
    la suite de regresión de la Fase 17): el "período actual" para
    prorratear NO es la posición absoluta en el calendario (ene 1-15 =
    período 1 aunque el contrato no exista todavía) -- es la posición
    RELATIVA al propio contrato dentro del año fiscal, contando desde
    la fecha de inicio del contrato (o desde el 1-ene si el contrato ya
    venía de un año anterior). Un contrato que arranca el 16-ene ya
    vale período 1 de 24 en su primera quincena (24 cuotas completas
    por delante), no período 2 de 24 (23 cuotas, como si el período 1
    ya se le hubiera consumido sin haber trabajado ahí). Se ancla a
    `contrato.fecha_inicio`, no al historial de planillas ya generadas
    en el sistema -- un contrato antiguo sin enero/febrero cargados
    todavía en el sistema sigue siendo período 3 en marzo, no período 1
    (ver test_contrato_que_arranca_a_mitad_de_anio_no_sobre_retiene y
    test_planilla_mensual_con_tres_empleados_distintos). El mecanismo
    de reconciliación contra lo ya retenido (para cambios de salario a
    mitad de año) no cambia -- solo cambia de dónde arranca a contar.
    """
    _numero_periodo_fiscal(tipo, periodo_inicio, periodo_fin)  # valida que el período calce
    periodos_por_anio = PERIODOS_POR_ANIO[tipo]
    inicio_fiscal_efectivo = max(
        contrato.fecha_inicio, datetime.date(periodo_inicio.year, 1, 1)
    )
    numero_periodo_inicio = _numero_periodo_de_fecha(tipo, inicio_fiscal_efectivo)
    numero_periodo_actual = _numero_periodo_de_fecha(tipo, periodo_inicio)
    numero_periodo = numero_periodo_actual - numero_periodo_inicio + 1
    periodos_restantes = periodos_por_anio - numero_periodo + 1

    renta_bruta_anual = salario_mensual_vigente * decimal.Decimal("12")

    parametro = parametros_isr_repo.obtener_vigente(db, periodo_fin)
    if parametro is None:
        # No debería pasar desde la migración 0015 (decimo confirmado
        # e integrado); si algún día no hay parámetro vigente para la
        # fecha (ej. período anterior al seed), se marca explícito en
        # vez de asumir en silencio que el décimo es exento.
        decimo_tratamiento = "no_configurado"
    elif parametro.decimo_incluido_en_base_gravable:
        decimo_tratamiento = "integrado"
        # El décimo son 3 partidas que suman un mes de salario al año
        # (CLAUDE.md sección 4); se usa el salario mensual vigente
        # como estimado de ese mes adicional (12 + 1 = 13 meses).
        renta_bruta_anual += salario_mensual_vigente
    else:
        decimo_tratamiento = "exento"

    # Confirmado por el contador: el excedente gravable se calcula
    # directo sobre la renta bruta anual (con décimo incluido), sin
    # restar CSS/SE de esa base.
    renta_gravable_anual = renta_bruta_anual

    tramo = tramos_isr_repo.obtener_tramo_aplicable(db, renta_gravable_anual, periodo_fin)
    if tramo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay un tramo de ISR vigente para el {periodo_fin.isoformat()} que cubra una "
            f"renta gravable anual de {renta_gravable_anual}. Verifica el seed de tramos_isr.",
        )
    impuesto_anual_proyectado = (
        tramo.impuesto_base + (renta_gravable_anual - tramo.monto_desde) * tramo.tasa_marginal
    ).quantize(_CENTAVO)

    ya_retenido_este_anio = movimientos_repo.sumar_isr_retenido_del_anio(
        db, contrato.id, periodo_inicio.year
    )

    isr_periodo = max(
        _CERO,
        (impuesto_anual_proyectado - ya_retenido_este_anio) / decimal.Decimal(periodos_restantes),
    ).quantize(_CENTAVO)

    auditoria = {
        "isr_renta_anual_proyectada": renta_bruta_anual.quantize(_CENTAVO),
        "isr_impuesto_anual_proyectado": impuesto_anual_proyectado,
        "isr_decimo_tratamiento": decimo_tratamiento,
        "isr_numero_periodo_anio": numero_periodo,
        "isr_periodos_restantes_anio": periodos_restantes,
    }
    return isr_periodo, auditoria


def _numero_periodo_de_fecha(tipo: str, fecha: datetime.date) -> int:
    """En qué período del año (1-12 mensual, 1-24 quincenal) cae una
    fecha cualquiera -- a diferencia de _numero_periodo_fiscal, no exige
    que la fecha sea exactamente el borde de inicio del período (una
    fecha de inicio de contrato puede caer cualquier día del mes).
    Usado solo para anclar el conteo relativo del ISR (ver corrección
    2026-08-18 en _calcular_isr_retenido)."""
    if tipo == "mensual":
        return fecha.month
    return (fecha.month - 1) * 2 + (1 if fecha.day <= 15 else 2)


def _numero_periodo_fiscal(
    tipo: str, periodo_inicio: datetime.date, periodo_fin: datetime.date
) -> tuple[int, int]:
    """Número de período (1-12 mensual, 1-24 quincenal) y períodos por
    año, asumiendo que el rango calza con un mes calendario completo o
    una quincena estándar (1-15 / 16-fin de mes). Si no calza, rechaza
    explícitamente en vez de adivinar -- el ISR depende de este número
    para prorratear correctamente."""
    ultimo_dia_mes = calendar.monthrange(periodo_inicio.year, periodo_inicio.month)[1]

    if tipo == "mensual":
        if periodo_inicio.day == 1 and periodo_fin == periodo_inicio.replace(day=ultimo_dia_mes):
            return periodo_inicio.month, PERIODOS_POR_ANIO["mensual"]
    elif tipo == "quincenal":
        if periodo_inicio.day == 1 and periodo_fin == periodo_inicio.replace(day=15):
            return (periodo_inicio.month - 1) * 2 + 1, PERIODOS_POR_ANIO["quincenal"]
        if periodo_inicio.day == 16 and periodo_fin == periodo_inicio.replace(day=ultimo_dia_mes):
            return (periodo_inicio.month - 1) * 2 + 2, PERIODOS_POR_ANIO["quincenal"]

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"El período {periodo_inicio.isoformat()} a {periodo_fin.isoformat()} no calza con un "
        "mes calendario completo ni con una quincena estándar (1-15 o 16-fin de mes); no se "
        "puede determinar el número de período fiscal para calcular el ISR.",
    )

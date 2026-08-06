import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, MovimientoPlanilla, Planilla, ProvisionDecimo
from app.repositories import contratos as contratos_repo
from app.repositories import historial_salarial as historial_repo
from app.repositories import movimientos_planilla as movimientos_repo
from app.repositories import planillas as planillas_repo
from app.repositories import provisiones_decimo as provisiones_decimo_repo
from app.repositories import tasas as tasas_repo
from app.services import ausencias_service

# Decreto de Gabinete N.221 de 1971, Art. 2: "Un día de salario por
# cada once (11) días, o fracción, de trabajo efectivo". El decreto
# original dice partidas el 15 de marzo/agosto/diciembre; la práctica
# actual (15 abr/ago/dic, label 'dic-abr' del schema) fue confirmada
# por el contador el 2026-08-05 -- ver FASE8-plan-decimo.txt.
DIAS_MES_COMERCIAL = decimal.Decimal("30")
DIVISOR_DECIMO = decimal.Decimal("11")
_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")

CUATRIMESTRES = ("dic-abr", "abr-ago", "ago-dic")


def _rango_cuatrimestre(cuatrimestre: str, anio: int) -> tuple[datetime.date, datetime.date]:
    if cuatrimestre == "dic-abr":
        return datetime.date(anio - 1, 12, 16), datetime.date(anio, 4, 15)
    if cuatrimestre == "abr-ago":
        return datetime.date(anio, 4, 16), datetime.date(anio, 8, 15)
    if cuatrimestre == "ago-dic":
        return datetime.date(anio, 8, 16), datetime.date(anio, 12, 15)
    raise ValueError(f"Cuatrimestre inválido: {cuatrimestre}")


def _fecha_pago_decretada(cuatrimestre: str, anio: int) -> datetime.date:
    if cuatrimestre == "dic-abr":
        return datetime.date(anio, 4, 15)
    if cuatrimestre == "abr-ago":
        return datetime.date(anio, 8, 15)
    if cuatrimestre == "ago-dic":
        return datetime.date(anio, 12, 15)
    raise ValueError(f"Cuatrimestre inválido: {cuatrimestre}")


def resolver_cuatrimestre(
    fecha: datetime.date,
) -> tuple[str, int, datetime.date, datetime.date]:
    """Determina en qué cuatrimestre de décimo cae `fecha`. `anio` es
    el año de PAGO de esa partida (ej. una fecha de enero cae en
    'dic-abr' del mismo año, que se paga en abril de ese año; una
    fecha del 20 de diciembre cae en el 'dic-abr' que se paga en abril
    del año SIGUIENTE)."""
    for anio_candidato in (fecha.year, fecha.year + 1):
        for cuatrimestre in CUATRIMESTRES:
            inicio, fin = _rango_cuatrimestre(cuatrimestre, anio_candidato)
            if inicio <= fecha <= fin:
                return cuatrimestre, anio_candidato, inicio, fin
    raise ValueError(f"No se pudo resolver el cuatrimestre de décimo para {fecha.isoformat()}")


def calcular_decimo_de_contrato(
    db: Session,
    contrato: Contrato,
    fecha_inicio_rango: datetime.date,
    fecha_corte: datetime.date,
) -> decimal.Decimal:
    """décimo = (días trabajados / 11) × salario_diario, recorriendo
    cada segmento de historial_salarial que se solapa con el rango
    (para que un cambio de salario a mitad de cuatrimestre se calcule
    con precisión, no con un promedio). "Días trabajados" resta los
    días de ausencias que no cuentan según ausencias_service (Fase 11)
    -- tratamiento por analogía a la regla de vacaciones del Código de
    Trabajo, PENDIENTE DE CONFIRMAR CON EL CONTADOR (el Decreto
    221/1971 propio del décimo no se pudo verificar, ver
    FASE11-plan-ausencias.txt)."""
    if fecha_corte < fecha_inicio_rango:
        return _CERO

    segmentos = historial_repo.listar_de_contrato(db, contrato.id)
    total = _CERO
    for segmento in segmentos:
        seg_fin = segmento.fecha_vigencia_hasta or fecha_corte
        efectivo_inicio = max(segmento.fecha_vigencia_desde, fecha_inicio_rango, contrato.fecha_inicio)
        efectivo_fin = min(seg_fin, fecha_corte, contrato.fecha_fin_real or fecha_corte)
        if efectivo_fin < efectivo_inicio:
            continue
        dias = decimal.Decimal((efectivo_fin - efectivo_inicio).days + 1)
        dias -= ausencias_service.dias_no_contables(
            db, contrato.id, efectivo_inicio, efectivo_fin, "decimo"
        )
        if dias < _CERO:
            dias = _CERO
        salario_diario = segmento.salario_base / DIAS_MES_COMERCIAL
        total += (dias / DIVISOR_DECIMO) * salario_diario

    return total.quantize(_CENTAVO)


def actualizar_provision(
    db: Session, empresa_id: uuid.UUID, contrato: Contrato, fecha_corte: datetime.date
) -> ProvisionDecimo | None:
    """Se llama desde planilla_service.generar_planilla al procesar
    cada contrato: si `fecha_corte` (periodo_fin de la planilla
    regular) cae dentro de un cuatrimestre de décimo, recalcula
    completo el acumulado de ese contrato para ese cuatrimestre (igual
    criterio que _recalcular_semana en Fase 5: nunca se suma
    incrementalmente, siempre se recalcula desde el inicio del
    cuatrimestre, así una planilla generada fuera de orden no
    descuadra la provisión)."""
    try:
        cuatrimestre, anio, inicio, _fin = resolver_cuatrimestre(fecha_corte)
    except ValueError:
        return None

    monto = calcular_decimo_de_contrato(db, contrato, inicio, fecha_corte)
    fecha_pago = _fecha_pago_decretada(cuatrimestre, anio)
    return provisiones_decimo_repo.upsert_provision(
        db, empresa_id, contrato.id, cuatrimestre, anio, monto, fecha_pago
    )


def listar_provisiones(db: Session, contrato_id: uuid.UUID) -> list[ProvisionDecimo]:
    return provisiones_decimo_repo.listar_de_contrato(db, contrato_id)


def generar_pago_decimo(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    cuatrimestre: str,
    anio: int,
    fecha_pago: datetime.date,
) -> Planilla:
    inicio, fin = _rango_cuatrimestre(cuatrimestre, anio)

    existente = planillas_repo.buscar_por_periodo(db, empresa_id, "decimo_tercer_mes", inicio, fin)
    if existente is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya existe un pago de décimo tercer mes ({cuatrimestre} {anio}) "
            f"(id={existente.id}, estado={existente.estado}). Anúlalo primero si necesitas "
            "regenerarlo.",
        )

    planilla = Planilla(
        empresa_id=empresa_id,
        tipo="decimo_tercer_mes",
        periodo_inicio=inicio,
        periodo_fin=fin,
        fecha_pago=fecha_pago,
        estado="borrador",
        procesada_por=usuario_id,
    )
    planillas_repo.crear(db, planilla)

    contratos = contratos_repo.listar_vigentes_en_periodo(db, empresa_id, inicio, fin)
    for contrato in contratos:
        # Recalcula fresco (no confía en que la provisión esté al día
        # si la última planilla regular del cuatrimestre no coincidió
        # exactamente con el cierre) -- así el pago y la provisión
        # quedan sincronizados por construcción antes de marcar pagado.
        monto = calcular_decimo_de_contrato(db, contrato, inicio, fin)
        provision = provisiones_decimo_repo.upsert_provision(
            db, empresa_id, contrato.id, cuatrimestre, anio, monto, fecha_pago
        )

        css_empleado = (monto * _factor_obligatorio(db, "decimo_empleado", fecha_pago)).quantize(
            _CENTAVO
        )
        css_patronal = (monto * _factor_obligatorio(db, "decimo_patronal", fecha_pago)).quantize(
            _CENTAVO
        )
        salario_neto = monto - css_empleado

        movimiento = MovimientoPlanilla(
            planilla_id=planilla.id,
            contrato_id=contrato.id,
            salario_base_periodo=monto,
            salario_bruto=monto,
            css_empleado=css_empleado,
            css_patronal=css_patronal,
            # Seguro Educativo no aplica al décimo: no hay tasa
            # decimo_seguro_educativo_* sembrada, y el decreto original
            # exime "ningún otro gravamen" salvo el ISR -- ver
            # FASE8-plan-decimo.txt.
            seguro_educativo_empleado=_CERO,
            seguro_educativo_patronal=_CERO,
            riesgo_profesional_patronal=_CERO,
            # El ISR del décimo ya se prorrateó por adelantado en los
            # pagos regulares del año (Fase 7: salario_mensual x 13);
            # retenerlo aquí también lo duplicaría.
            isr_retenido=_CERO,
            otras_deducciones=_CERO,
            salario_neto=salario_neto,
        )
        movimientos_repo.crear(db, movimiento)
        provisiones_decimo_repo.marcar_pagada(db, provision, movimiento.id, fecha_pago)

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5/6 (SET
    # LOCAL app.empresa_actual no sobrevive al commit).
    return planilla


def _factor_obligatorio(db: Session, tipo_tasa: str, fecha: datetime.date) -> decimal.Decimal:
    tasa = tasas_repo.obtener_tasa_vigente(db, tipo_tasa, fecha)
    if tasa is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay una tasa vigente para '{tipo_tasa}' en la fecha {fecha.isoformat()}. "
            "Verifica el seed de tasas_vigentes.",
        )
    return tasa.tasa

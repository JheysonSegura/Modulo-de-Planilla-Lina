import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, Liquidacion
from app.repositories import historial_salarial as historial_repo
from app.repositories import liquidaciones as liquidaciones_repo
from app.repositories import movimientos_planilla as movimientos_repo
from app.services import decimo_service, vacaciones_service

# Código de Trabajo, Título VI (Art. 210-229D), verificado contra
# código-detrabajo.pdf el 2026-08-05 -- ver FASE10-plan-liquidaciones.txt
# para el detalle completo de qué articulo respalda cada concepto y
# las limitaciones documentadas (salarios caídos, penalidad del
# Art. 222, obra_determinada sin fecha de fin).
DIAS_MES_COMERCIAL = decimal.Decimal("30")
DIAS_ANIO = decimal.Decimal("365")
DIAS_SEIS_MESES = 182
DIAS_TREINTA = 30
DIAS_CINCO_ANIOS = 1825
SEMANA = decimal.Decimal("7")
_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")

MOTIVOS_VALIDOS = {
    "renuncia_voluntaria",
    "renuncia_justificada",
    "despido_justificado",
    "despido_causa_economica",
    "despido_injustificado",
    "mutuo_acuerdo",
}
# Art. 223 (renuncia justificada), Art. 213-C in fine (causa económica,
# ver Art. 225) y Art. 210.8 (despido injustificado) dan derecho a la
# indemnización del Art. 225/227. Los demás motivos, no.
MOTIVOS_CON_INDEMNIZACION = {
    "renuncia_justificada",
    "despido_causa_economica",
    "despido_injustificado",
}
# Art. 214: preaviso de 30 días cuando el empleador termina sin culpa
# del trabajador (causa económica) o sin causa justificada.
MOTIVOS_CON_PREAVISO = {"despido_causa_economica", "despido_injustificado"}


def _salario_mensual_vigente(
    db: Session, contrato: Contrato, fecha: datetime.date
) -> decimal.Decimal:
    registro = historial_repo.get_vigente_en_fecha(db, contrato.id, fecha)
    if registro is None:
        registro = historial_repo.get_abierto(db, contrato.id)
    if registro is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay salario registrado para este contrato en la fecha {fecha.isoformat()}.",
        )
    return registro.salario_base


def _salario_diario_vigente(db: Session, contrato: Contrato, fecha: datetime.date) -> decimal.Decimal:
    return _salario_mensual_vigente(db, contrato, fecha) / DIAS_MES_COMERCIAL


def _suma_movimientos(
    db: Session, contrato: Contrato, fecha_hasta: datetime.date, dias_ventana: int
) -> decimal.Decimal:
    fecha_desde_exclusive = fecha_hasta - datetime.timedelta(days=dias_ventana)
    return movimientos_repo.sumar_salario_bruto_periodo(
        db, contrato.id, fecha_desde_exclusive, fecha_hasta
    )


def _salario_base_indemnizacion(
    db: Session, contrato: Contrato, fecha: datetime.date
) -> decimal.Decimal:
    """Art. 149 CT: promedio percibido (ordinario + extraordinario
    efectivamente trabajado) de los últimos 6 meses o 30 días, el que
    sea más favorable al trabajador. Usa movimientos_planilla.salario_bruto
    real (incluye horas extra/variables); si no hay historial de
    planillas para este contrato, cae al salario_base vigente."""
    promedio_6_meses = _suma_movimientos(db, contrato, fecha, DIAS_SEIS_MESES) / decimal.Decimal("6")
    promedio_30_dias = _suma_movimientos(db, contrato, fecha, DIAS_TREINTA)
    base = max(promedio_6_meses, promedio_30_dias)
    if base <= _CERO:
        base = _salario_mensual_vigente(db, contrato, fecha)
    return base


def _salario_base_prima_antiguedad(
    db: Session, contrato: Contrato, fecha: datetime.date
) -> decimal.Decimal:
    """Art. 226 CT: promedio de la remuneración total percibida durante
    los últimos CINCO AÑOS trabajados (o el tiempo realmente trabajado,
    si es menor) -- ventana distinta a la del Art. 149. Se promedia
    sobre el tramo que realmente tiene movimientos_planilla cargados
    (no sobre toda la antigüedad del contrato): un contrato con 3 años
    de antigüedad pero solo 2 meses de planillas en este sistema no
    debe diluir el promedio dividiendo entre 36 meses. Cae al
    salario_base vigente si no hay ningún movimiento."""
    fecha_desde_exclusive = fecha - datetime.timedelta(days=DIAS_CINCO_ANIOS)
    suma = movimientos_repo.sumar_salario_bruto_periodo(db, contrato.id, fecha_desde_exclusive, fecha)
    if suma <= _CERO:
        return _salario_mensual_vigente(db, contrato, fecha)
    fecha_min = movimientos_repo.obtener_fecha_minima_periodo(
        db, contrato.id, fecha_desde_exclusive, fecha
    )
    inicio_promedio = max(fecha_min, contrato.fecha_inicio)
    dias = max((fecha - inicio_promedio).days + 1, 1)
    meses = decimal.Decimal(dias) / DIAS_MES_COMERCIAL
    return suma / meses


def _calcular_salario_pendiente(
    db: Session, contrato: Contrato, fecha_terminacion: datetime.date
) -> decimal.Decimal:
    ultimo_periodo_fin = movimientos_repo.obtener_ultimo_periodo_fin_pagado(db, contrato.id)
    fecha_desde = (
        ultimo_periodo_fin + datetime.timedelta(days=1)
        if ultimo_periodo_fin is not None
        else contrato.fecha_inicio
    )
    if fecha_terminacion < fecha_desde:
        return _CERO
    dias = (fecha_terminacion - fecha_desde).days + 1
    return (decimal.Decimal(dias) * _salario_diario_vigente(db, contrato, fecha_terminacion)).quantize(
        _CENTAVO
    )


def _calcular_prima_antiguedad(
    db: Session, contrato: Contrato, fecha_terminacion: datetime.date
) -> decimal.Decimal:
    """Art. 224 CT: 1 semana de salario por año laborado (proporcional
    el año incompleto), SOLO para contratos por tiempo indefinido,
    cualquiera que sea el motivo de terminación."""
    if contrato.tipo_contrato != "indefinido":
        return _CERO
    dias_totales = (fecha_terminacion - contrato.fecha_inicio).days + 1
    if dias_totales <= 0:
        return _CERO
    anios = decimal.Decimal(dias_totales) / DIAS_ANIO
    salario_semanal = _salario_base_prima_antiguedad(db, contrato, fecha_terminacion) / DIAS_MES_COMERCIAL * SEMANA
    return (anios * salario_semanal).quantize(_CENTAVO)


def _indemnizacion_escala_c(anios: decimal.Decimal, salario_semanal: decimal.Decimal) -> decimal.Decimal:
    """Art. 225-C CT: única escala aplicable a relaciones de trabajo
    vigentes hoy (las escalas A/B son para tiempo de servicios anterior
    al 2-abr-1972). 3.4 semanas/año en los primeros 10 años + 1
    semana/año adicional después."""
    diez = decimal.Decimal("10")
    if anios <= diez:
        semanas = anios * decimal.Decimal("3.4")
    else:
        semanas = diez * decimal.Decimal("3.4") + (anios - diez)
    return (semanas * salario_semanal).quantize(_CENTAVO)


def _calcular_indemnizacion(
    db: Session, contrato: Contrato, motivo: str, fecha_terminacion: datetime.date
) -> decimal.Decimal:
    if motivo not in MOTIVOS_CON_INDEMNIZACION:
        return _CERO

    if contrato.tipo_contrato == "indefinido":
        dias_totales = max((fecha_terminacion - contrato.fecha_inicio).days + 1, 0)
        anios = decimal.Decimal(dias_totales) / DIAS_ANIO
        salario_semanal = (
            _salario_base_indemnizacion(db, contrato, fecha_terminacion) / DIAS_MES_COMERCIAL * SEMANA
        )
        return _indemnizacion_escala_c(anios, salario_semanal)

    if contrato.tipo_contrato == "definido":
        # Art. 227 CT: solo cubre despido SIN JUSTA CAUSA antes del
        # vencimiento del plazo. No hay fundamento revisado para
        # renuncia_justificada/despido_causa_economica en contratos
        # definidos -- se deja en 0 (limitación documentada).
        if motivo != "despido_injustificado":
            return _CERO
        if contrato.fecha_fin_pactada is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Este contrato definido no tiene fecha_fin_pactada; no se puede calcular "
                "la indemnización del Art. 227 CT (salarios del tiempo restante).",
            )
        if contrato.fecha_fin_pactada <= fecha_terminacion:
            return _CERO
        dias_restantes = (contrato.fecha_fin_pactada - fecha_terminacion).days
        salario_diario = _salario_mensual_vigente(db, contrato, fecha_terminacion) / DIAS_MES_COMERCIAL
        return (decimal.Decimal(dias_restantes) * salario_diario).quantize(_CENTAVO)

    # obra_determinada: sin fecha de fin estimable en este proyecto.
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "No se puede calcular automáticamente la indemnización de un contrato por obra "
        "determinada (Art. 227 CT) sin una fecha de fin estimada. Regístrala manualmente "
        "vía otras_deducciones/ajuste posterior.",
    )


def _calcular_preaviso(
    db: Session, contrato: Contrato, motivo: str, fecha_terminacion: datetime.date
) -> decimal.Decimal:
    if motivo not in MOTIVOS_CON_PREAVISO:
        return _CERO
    return (decimal.Decimal("30") * _salario_diario_vigente(db, contrato, fecha_terminacion)).quantize(
        _CENTAVO
    )


def generar_liquidacion(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    motivo: str,
    fecha_terminacion: datetime.date,
    otras_deducciones: decimal.Decimal = _CERO,
) -> Liquidacion:
    if motivo not in MOTIVOS_VALIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Motivo de terminación inválido: {motivo}"
        )
    if fecha_terminacion < contrato.fecha_inicio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "fecha_terminacion no puede ser anterior al inicio del contrato.",
        )
    if contrato.estado == "terminado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este contrato ya está terminado.")

    salario_pendiente = _calcular_salario_pendiente(db, contrato, fecha_terminacion)

    # Reutiliza los servicios de Fase 8/9 tal cual -- ambos recalculan
    # completo su provisión hasta fecha_terminacion y la devuelven, sin
    # duplicar la lógica de días/11 aquí.
    decimo_service.actualizar_provision(db, empresa_id, contrato, fecha_terminacion)
    decimo_proporcional = sum(
        (
            provision.monto_acumulado
            for provision in decimo_service.listar_provisiones(db, contrato.id)
            if not provision.pagado
        ),
        _CERO,
    ).quantize(_CENTAVO)

    provision_vacaciones = vacaciones_service.actualizar_provision(
        db, empresa_id, contrato, fecha_terminacion
    )
    vacaciones_pendientes = provision_vacaciones.monto_provisionado

    prima_antiguedad = _calcular_prima_antiguedad(db, contrato, fecha_terminacion)
    indemnizacion = _calcular_indemnizacion(db, contrato, motivo, fecha_terminacion)
    preaviso = _calcular_preaviso(db, contrato, motivo, fecha_terminacion)

    monto_total = (
        salario_pendiente
        + decimo_proporcional
        + vacaciones_pendientes
        + prima_antiguedad
        + indemnizacion
        + preaviso
        - otras_deducciones
    ).quantize(_CENTAVO)

    liquidacion = Liquidacion(
        empresa_id=empresa_id,
        contrato_id=contrato.id,
        fecha_terminacion=fecha_terminacion,
        motivo=motivo,
        salario_pendiente=salario_pendiente,
        decimo_proporcional=decimo_proporcional,
        vacaciones_pendientes=vacaciones_pendientes,
        prima_antiguedad=prima_antiguedad,
        indemnizacion=indemnizacion,
        preaviso=preaviso,
        otras_deducciones=otras_deducciones,
        monto_total=monto_total,
        estado="borrador",
    )
    liquidaciones_repo.crear(db, liquidacion)

    contrato.estado = "terminado"
    contrato.fecha_fin_real = fecha_terminacion
    contrato.motivo_terminacion = motivo

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto
    # (SET LOCAL app.empresa_actual no sobrevive al commit).
    return liquidacion


def listar_liquidaciones(db: Session, contrato_id: uuid.UUID) -> list[Liquidacion]:
    return liquidaciones_repo.listar_de_contrato(db, contrato_id)

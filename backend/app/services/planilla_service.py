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
from app.repositories import planillas as planillas_repo
from app.repositories import tasas as tasas_repo

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

    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5 (SET LOCAL
    # app.empresa_actual no sobrevive al commit). planilla ya tiene sus
    # campos poblados en Python desde antes del commit.
    return planilla


def obtener_planilla(db: Session, planilla_id: uuid.UUID) -> Planilla:
    planilla = planillas_repo.get(db, planilla_id)
    if planilla is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planilla no encontrada")
    return planilla


def listar_movimientos(db: Session, planilla_id: uuid.UUID) -> list[MovimientoPlanilla]:
    return movimientos_repo.listar_de_planilla(db, planilla_id)


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
        if tipo == "mensual":
            salario_base_periodo = salario_mensual
        else:
            salario_base_periodo = (salario_mensual / decimal.Decimal("2")).quantize(_CENTAVO)
    else:
        dias_inicio_efectivo = max(contrato.fecha_inicio, periodo_inicio)
        dias_fin_efectivo = min(contrato.fecha_fin_real or periodo_fin, periodo_fin)
        dias_trabajados = (dias_fin_efectivo - dias_inicio_efectivo).days + 1
        salario_base_periodo = (salario_diario * decimal.Decimal(dias_trabajados)).quantize(_CENTAVO)

    conceptos: list[ConceptoVariable] = []

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
        # tasas_riesgo_profesional no tiene datos sembrados todavía
        # (pendiente de la tabla oficial de la CSS, CLAUDE.md sección
        # 4/6): None es un estado normal por ahora, no un error.
        if tasa_riesgo is not None:
            riesgo_profesional_patronal = (base_gravable * tasa_riesgo.tasa).quantize(_CENTAVO)

    isr_retenido = _calcular_isr_retenido(base_gravable, periodo_fin)

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


def _calcular_isr_retenido(base_gravable: decimal.Decimal, fecha: datetime.date) -> decimal.Decimal:
    """Placeholder deliberado: el ISR se implementa en una fase aparte
    (CLAUDE.md sección 6 -- anualización, y su interacción todavía sin
    confirmar con el décimo). Vive como paso aislado del pipeline para
    que esa fase lo reemplace sin tocar el resto de este servicio."""
    return _CERO

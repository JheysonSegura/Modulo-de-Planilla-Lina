import calendar
import dataclasses
import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ConceptoVariable, Contrato, CuotaDescuento, DescuentoRecurrente, Empresa
from app.repositories import descuentos as descuentos_repo
from app.repositories import tasas as tasas_repo
from app.schemas.descuentos import (
    CuotaDescuentoOut,
    DescuentoCreate,
    DescuentoOut,
    SimulacionDescuentoOut,
)
from app.services import auditoria_service, salario_minimo_service

# Descuentos del Art. 161 CT, verificado contra código-detrabajo.pdf el
# 2026-11-17 -- ver PLAN-descuentos-prestamos.md. Decisiones del usuario
# ese día: se cobran del salario NETO (después de CSS, Seguro Educativo e
# ISR), en las quincenas y en el pago de vacaciones (nunca en el décimo);
# pasar un tope solo genera un aviso, pero el neto nunca queda negativo.
ETIQUETAS = {
    "prestamo_empresa": "Préstamo de la empresa",
    "prestamo_bancario": "Préstamo bancario / financiera",
    "hipoteca": "Hipoteca / vivienda",
    "cooperativa": "Cooperativa / ahorro",
    "pension_alimenticia": "Pensión alimenticia",
    "embargo": "Embargo",
}
TIPOS_DESCUENTO = frozenset(ETIQUETAS)
# Corrección del usuario 2026-11-17: solo el préstamo de la empresa se
# calcula (monto + plazo -> cuota; solo capital, sin intereses, Art. 165
# CT). Los demás llevan la cuota que indica la carta u orden, tal cual, y
# el n.º de pagos (obligatorio) -- el sistema no calcula la cuota.

# Tope individual por tipo (tasas_vigentes, nunca hardcodeado) y el
# artículo que lo fija, para el aviso.
_TOPE_POR_TIPO = {
    "prestamo_empresa": ("tope_desc_prestamo_empresa", "161.3"),
    "prestamo_bancario": ("tope_desc_prestamo_bancario", "161.11"),
    "hipoteca": ("tope_desc_hipoteca", "161.4"),
}
_TOPE_EMBARGO = "tope_desc_embargo_excedente"
_TOPE_TOTAL = "tope_desc_total"
# Art. 161.13: la pensión alimenticia queda fuera del tope del 50%.
_FUERA_DEL_TOPE_TOTAL = {"pension_alimenticia"}

# Las órdenes de autoridad se cobran primero si el neto no alcanza para
# todo; el resto en el orden en que se registraron.
_PRIORIDAD = {"pension_alimenticia": 0, "embargo": 1}

_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")
_TREINTA = decimal.Decimal("30")


def _bal(monto: decimal.Decimal) -> str:
    return f"B/.{monto:,.2f}"


def fechas_de_cobro(
    frecuencia: str, desde: datetime.date, hasta: datetime.date
) -> list[datetime.date]:
    """Quincenal: el 15 y el último día de cada mes. Mensual: el último
    día de cada mes. Una planilla cobra las fechas que caen en su período."""
    fechas = []
    anio, mes = desde.year, desde.month
    while datetime.date(anio, mes, 1) <= hasta:
        ultimo = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])
        candidatas = [datetime.date(anio, mes, 15), ultimo] if frecuencia == "quincenal" else [ultimo]
        fechas.extend(f for f in candidatas if desde <= f <= hasta)
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return fechas


def calcular_plan(
    monto_total: decimal.Decimal, plazo_meses: int, frecuencia: str
) -> tuple[int, decimal.Decimal, decimal.Decimal]:
    """(n.º de cuotas, cuota, última cuota). La cuota se trunca al centavo
    y la última absorbe la diferencia, para que el total cuadre exacto."""
    numero_cuotas = plazo_meses * (2 if frecuencia == "quincenal" else 1)
    cuota = (monto_total / numero_cuotas).quantize(_CENTAVO, rounding=decimal.ROUND_DOWN)
    if cuota <= _CERO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El monto {_bal(monto_total)} es muy pequeño para {numero_cuotas} cuotas.",
        )
    ultima = monto_total - cuota * (numero_cuotas - 1)
    return numero_cuotas, cuota, ultima


def simular(
    frecuencia: str,
    fecha_inicio: datetime.date,
    monto_total: decimal.Decimal | None = None,
    plazo_meses: int | None = None,
    cuota: decimal.Decimal | None = None,
    numero_cuotas: int | None = None,
) -> SimulacionDescuentoOut:
    """Préstamo de la empresa: calcula la cuota con monto y plazo. Externo:
    la cuota y el n.º de pagos vienen de la carta; solo se calculan las
    fechas de cobro y el total."""
    if monto_total is not None and plazo_meses is not None:
        numero_cuotas, cuota, ultima = calcular_plan(monto_total, plazo_meses, frecuencia)
    else:
        ultima = cuota
        monto_total = cuota * numero_cuotas
    meses = numero_cuotas if frecuencia == "mensual" else (numero_cuotas + 1) // 2
    hasta = fecha_inicio + datetime.timedelta(days=31 * (meses + 1))
    fechas = fechas_de_cobro(frecuencia, fecha_inicio, hasta)[:numero_cuotas]
    return SimulacionDescuentoOut(
        monto_total=monto_total,
        numero_cuotas=numero_cuotas,
        cuota=cuota,
        ultima_cuota=ultima,
        fecha_primera_cuota=fechas[0],
        fecha_ultima_cuota=fechas[-1],
    )


def _ultima_cuota(descuento: DescuentoRecurrente) -> decimal.Decimal:
    return descuento.monto_total - descuento.cuota * (descuento.numero_cuotas - 1)


def saldo(db: Session, descuento: DescuentoRecurrente) -> decimal.Decimal | None:
    """None si el descuento no tiene monto total (pensión, cooperativa)."""
    if descuento.monto_total is None:
        return None
    return max(descuento.monto_total - descuentos_repo.sumar_cobrado(db, descuento.id), _CERO)


def resumen(db: Session, descuento: DescuentoRecurrente, contrato: Contrato) -> DescuentoOut:
    saldo_actual = saldo(db, descuento)
    if descuento.estado == "cerrado":
        estado_actual = "cerrado"
    elif saldo_actual is not None and saldo_actual <= _CERO:
        estado_actual = "pagado"
    elif contrato.estado == "terminado":
        estado_actual = "terminado"
    else:
        estado_actual = "activo"
    return DescuentoOut.model_validate(descuento).model_copy(
        update={
            "total_cobrado": descuentos_repo.sumar_cobrado(db, descuento.id),
            "saldo": saldo_actual,
            "cuotas_cobradas": descuentos_repo.contar_cobros(db, descuento.id),
            "estado_actual": estado_actual,
        }
    )


def listar_descuentos(db: Session, contrato: Contrato) -> list[DescuentoOut]:
    return [resumen(db, d, contrato) for d in descuentos_repo.listar_de_contrato(db, contrato.id)]


def obtener_descuento(db: Session, descuento_id: uuid.UUID) -> DescuentoRecurrente:
    descuento = descuentos_repo.get(db, descuento_id)
    if descuento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Descuento no encontrado")
    return descuento


def registrar_descuento(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID | None,
    contrato: Contrato,
    datos: DescuentoCreate,
) -> DescuentoOut:
    if contrato.estado == "terminado":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El contrato está terminado; no se le pueden agregar descuentos."
        )
    if datos.fecha_inicio < contrato.fecha_inicio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fecha del primer cobro no puede ser anterior al inicio del contrato.",
        )

    monto_total = datos.monto_total
    numero_cuotas = datos.numero_cuotas
    cuota = datos.cuota
    if datos.tipo == "prestamo_empresa":
        numero_cuotas, cuota, _ = calcular_plan(datos.monto_total, datos.plazo_meses, datos.frecuencia)
    elif numero_cuotas is not None:
        # Total a descontar según la carta (cuota × pagos), para llevar el
        # saldo y detener el cobro solo al llegar al último pago. Sin n.º de
        # pagos (solo pensión/cooperativa) no hay saldo: sigue hasta cerrarse.
        monto_total = cuota * numero_cuotas

    descuento = descuentos_repo.crear(
        db,
        DescuentoRecurrente(
            empresa_id=empresa_id,
            contrato_id=contrato.id,
            tipo=datos.tipo,
            acreedor=datos.acreedor.strip(),
            referencia=datos.referencia,
            monto_total=monto_total,
            plazo_meses=datos.plazo_meses,
            frecuencia=datos.frecuencia,
            numero_cuotas=numero_cuotas,
            cuota=cuota,
            fecha_inicio=datos.fecha_inicio,
            estado="activo",
            observacion=datos.observacion,
            registrado_por_usuario_id=usuario_id,
        ),
    )
    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "descuentos_recurrentes",
        descuento.id,
        "creado",
        empleado_id=contrato.empleado_id,
        datos_nuevos={
            "tipo": descuento.tipo,
            "acreedor": descuento.acreedor,
            "monto_total": str(descuento.monto_total) if descuento.monto_total else None,
            "plazo_meses": descuento.plazo_meses,
            "frecuencia": descuento.frecuencia,
            "cuota": str(descuento.cuota),
            "fecha_inicio": descuento.fecha_inicio.isoformat(),
        },
    )
    resultado = resumen(db, descuento, contrato)
    db.commit()
    # Sin db.refresh(): rompería RLS igual que en el resto del proyecto.
    return resultado


def cerrar_descuento(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    descuento: DescuentoRecurrente,
    contrato: Contrato,
    motivo: str,
    fecha_cierre: datetime.date | None,
) -> DescuentoOut:
    """Deja de cobrarse desde ya (ej. carta de cancelación del banco,
    orden judicial que levanta un embargo). Las cuotas ya cobradas no se
    tocan."""
    if descuento.estado != "activo":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este descuento ya está cerrado.")
    descuento.estado = "cerrado"
    descuento.motivo_cierre = motivo.strip()
    descuento.fecha_cierre = fecha_cierre or datetime.date.today()
    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "descuentos_recurrentes",
        descuento.id,
        "cerrado",
        empleado_id=contrato.empleado_id,
        datos_anteriores={"estado": "activo"},
        datos_nuevos={
            "estado": "cerrado",
            "motivo": descuento.motivo_cierre,
            "fecha_cierre": descuento.fecha_cierre.isoformat(),
        },
    )
    resultado = resumen(db, descuento, contrato)
    db.commit()
    return resultado


def eliminar_descuento(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    descuento: DescuentoRecurrente,
    contrato: Contrato,
) -> None:
    """Solo para corregir un registro equivocado que todavía no cobró
    nada (ni siquiera en una planilla luego anulada). Con cuotas, se cierra."""
    if descuentos_repo.tiene_cuotas(db, descuento.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este descuento ya tiene cuotas en alguna planilla; no se puede borrar. Ciérralo.",
        )
    auditoria_service.registrar(
        db,
        empresa_id,
        usuario_id,
        "descuentos_recurrentes",
        descuento.id,
        "eliminado",
        empleado_id=contrato.empleado_id,
        datos_anteriores={
            "tipo": descuento.tipo,
            "acreedor": descuento.acreedor,
            "cuota": str(descuento.cuota),
        },
    )
    db.delete(descuento)
    db.commit()


def actualizar_documento(
    db: Session,
    descuento: DescuentoRecurrente,
    contrato: Contrato,
    contenido: bytes,
    content_type: str,
    nombre_archivo: str,
) -> DescuentoOut:
    descuento.documento = contenido
    descuento.documento_content_type = content_type
    descuento.documento_nombre_archivo = nombre_archivo
    resultado = resumen(db, descuento, contrato)
    db.commit()
    return resultado


def listar_cuotas(db: Session, descuento: DescuentoRecurrente) -> list[CuotaDescuentoOut]:
    cuotas = []
    for cuota, planilla, liquidacion in descuentos_repo.listar_cuotas_con_origen(db, descuento.id):
        origen = planilla.tipo if planilla is not None else "liquidacion"
        anulada = (planilla or liquidacion).estado == "anulada"
        cuotas.append(
            CuotaDescuentoOut(
                id=cuota.id,
                fecha_cobro=cuota.fecha_cobro,
                monto=cuota.monto,
                monto_programado=cuota.monto_programado,
                origen=origen,
                planilla_id=planilla.id if planilla is not None else None,
                liquidacion_id=liquidacion.id if liquidacion is not None else None,
                anulada=anulada,
            )
        )
    return cuotas


@dataclasses.dataclass
class CobroPeriodo:
    cuotas: list[CuotaDescuento]
    conceptos: list[ConceptoVariable]
    total: decimal.Decimal
    advertencias: list[str]


def _descripcion_concepto(descuento: DescuentoRecurrente, numeros: list[int]) -> str:
    texto = f"{ETIQUETAS[descuento.tipo]} — {descuento.acreedor}"
    if descuento.referencia:
        texto += f" (ref. {descuento.referencia})"
    if descuento.numero_cuotas:
        if len(numeros) == 1:
            texto += f", cuota {numeros[0]} de {descuento.numero_cuotas}"
        else:
            lista = ", ".join(str(n) for n in numeros[:-1]) + f" y {numeros[-1]}"
            texto += f", cuotas {lista} de {descuento.numero_cuotas}"
    return texto


def cobrar_en_periodo(
    db: Session,
    empresa: Empresa,
    contrato: Contrato,
    desde: datetime.date,
    hasta: datetime.date,
    neto_antes_de_descuentos: decimal.Decimal,
    otras_deducciones: decimal.Decimal,
    fraccion_mes: decimal.Decimal,
    fecha_referencia: datetime.date,
) -> CobroPeriodo:
    """Cuotas de los descuentos activos del contrato cuyas fechas de cobro
    caen en [desde, hasta] y que ninguna planilla no anulada cobró ya (ej.
    las que cobró el pago de vacaciones no se repiten en la quincena).

    `neto_antes_de_descuentos` = bruto − CSS − SE − ISR del pago: es la
    base de los topes (decisión del usuario 2026-11-17). Lo que queda tras
    `otras_deducciones` (descuentos puntuales ya capturados) es lo
    disponible: si no alcanza, la cuota se cobra en parte y la diferencia
    sigue en el saldo -- el neto nunca queda negativo. `fraccion_mes` es la
    parte del mes que paga este pago (15/30 en una quincena, días/30 en
    vacaciones), para el mínimo inembargable del embargo.

    Los cobros posteriores a la terminación del contrato no se hacen: cada
    persona sigue pagando por su cuenta (decisión del usuario 2026-11-17)."""
    limite = min(hasta, contrato.fecha_fin_real) if contrato.fecha_fin_real else hasta
    descuentos = sorted(
        descuentos_repo.listar_activos_de_contrato(db, contrato.id, limite),
        key=lambda d: _PRIORIDAD.get(d.tipo, 2),
    )
    disponible = max(neto_antes_de_descuentos - otras_deducciones, _CERO)
    cuotas: list[CuotaDescuento] = []
    conceptos: list[ConceptoVariable] = []
    advertencias: list[str] = []
    por_tipo: dict[str, decimal.Decimal] = {}

    for descuento in descuentos:
        saldo_actual = saldo(db, descuento)
        numeros: list[int] = []
        cobrado = _CERO
        nombre = f"{ETIQUETAS[descuento.tipo]} ({descuento.acreedor})"
        for fecha in fechas_de_cobro(descuento.frecuencia, max(desde, descuento.fecha_inicio), limite):
            if saldo_actual is not None and saldo_actual <= _CERO:
                break
            if descuentos_repo.existe_cobro_en_fecha(db, descuento.id, fecha):
                continue
            numero = descuentos_repo.contar_cobros_antes_de(db, descuento.id, fecha) + len(numeros) + 1
            programado = descuento.cuota
            if descuento.numero_cuotas and numero == descuento.numero_cuotas:
                programado = _ultima_cuota(descuento)
            if saldo_actual is not None:
                programado = min(programado, saldo_actual)
            monto = min(programado, disponible)
            if monto <= _CERO:
                advertencias.append(
                    f"{nombre}: no se cobró la cuota del {fecha.isoformat()} ({_bal(programado)}) "
                    "porque no quedaba neto disponible; queda en el saldo."
                )
            elif monto < programado:
                advertencias.append(
                    f"{nombre}: del cobro del {fecha.isoformat()} se descontó {_bal(monto)} de "
                    f"{_bal(programado)} porque el neto no alcanzaba; la diferencia queda en el saldo."
                )
            if monto <= _CERO:
                continue
            cuotas.append(
                CuotaDescuento(
                    empresa_id=empresa.id,
                    descuento_id=descuento.id,
                    fecha_cobro=fecha,
                    monto=monto,
                    monto_programado=programado,
                )
            )
            numeros.append(numero)
            cobrado += monto
            disponible -= monto
            if saldo_actual is not None:
                saldo_actual -= monto
        if cobrado > _CERO:
            conceptos.append(
                ConceptoVariable(
                    tipo="deduccion",
                    codigo=descuento.tipo,
                    descripcion=_descripcion_concepto(descuento, numeros),
                    monto=cobrado,
                )
            )
            por_tipo[descuento.tipo] = por_tipo.get(descuento.tipo, _CERO) + cobrado

    advertencias.extend(
        _advertencias_de_topes(db, empresa, contrato, por_tipo, neto_antes_de_descuentos,
                               fraccion_mes, fecha_referencia)
    )
    return CobroPeriodo(
        cuotas=cuotas,
        conceptos=conceptos,
        total=sum(por_tipo.values(), _CERO),
        advertencias=advertencias,
    )


def _tasa(db: Session, clave: str, fecha: datetime.date) -> decimal.Decimal | None:
    tasa = tasas_repo.obtener_tasa_vigente(db, clave, fecha)
    return tasa.tasa if tasa is not None else None


def _porcentaje(tasa: decimal.Decimal) -> str:
    return f"{(tasa * 100).normalize():f}%"


def _advertencias_de_topes(
    db: Session,
    empresa: Empresa,
    contrato: Contrato,
    por_tipo: dict[str, decimal.Decimal],
    neto: decimal.Decimal,
    fraccion_mes: decimal.Decimal,
    fecha: datetime.date,
) -> list[str]:
    """Solo avisos (decisión del usuario 2026-11-17): la cuota se cobra
    completa aunque pase el tope."""
    advertencias = []
    base = max(neto, _CERO)
    for tipo, (clave, articulo) in _TOPE_POR_TIPO.items():
        monto = por_tipo.get(tipo, _CERO)
        tasa = _tasa(db, clave, fecha)
        if monto > _CERO and tasa is not None and monto > (base * tasa).quantize(_CENTAVO):
            advertencias.append(
                f"{ETIQUETAS[tipo]}: {_bal(monto)} supera el {_porcentaje(tasa)} del salario neto "
                f"({_bal(base)}) que permite el Art. {articulo} CT."
            )

    embargo = por_tipo.get("embargo", _CERO)
    tasa_embargo = _tasa(db, _TOPE_EMBARGO, fecha)
    if embargo > _CERO and tasa_embargo is not None:
        minimo = salario_minimo_service.salario_minimo_mensual(
            db, empresa, fecha, contrato.jornada_horas_semana
        )
        if minimo is None:
            advertencias.append(
                "Embargo: no se pudo verificar el tope porque no se resolvió el salario mínimo "
                "de la empresa (revisa región, actividad y tamaño en los datos de la empresa)."
            )
        else:
            minimo_periodo = (minimo * fraccion_mes).quantize(_CENTAVO)
            tope = (max(base - minimo_periodo, _CERO) * tasa_embargo).quantize(_CENTAVO)
            if embargo > tope:
                advertencias.append(
                    f"Embargo: {_bal(embargo)} supera el {_porcentaje(tasa_embargo)} de lo que el "
                    f"neto excede el salario mínimo del período ({_bal(minimo_periodo)}); tope "
                    f"{_bal(tope)} según el Art. 161.7 y 162 CT."
                )

    tasa_total = _tasa(db, _TOPE_TOTAL, fecha)
    total = sum((m for t, m in por_tipo.items() if t not in _FUERA_DEL_TOPE_TOTAL), _CERO)
    if total > _CERO and tasa_total is not None and total > (base * tasa_total).quantize(_CENTAVO):
        advertencias.append(
            f"El total de descuentos ({_bal(total)}, sin contar pensión alimenticia) supera el "
            f"{_porcentaje(tasa_total)} del salario neto ({_bal(base)}) que permite el Art. 161.13 CT."
        )
    return advertencias


def fin_de_cobro_de_vacaciones(fecha_fin_goce: datetime.date) -> datetime.date:
    """El descanso se cuenta en base comercial (CLAUDE.md, vacaciones):
    si termina el día 30 de un mes de 31, cubre también el cobro de fin
    de mes."""
    siguiente = fecha_fin_goce + datetime.timedelta(days=1)
    if fecha_fin_goce.day == 30 and siguiente.day == 31:
        return siguiente
    return fecha_fin_goce


def saldo_prestamos_empresa(db: Session, contrato: Contrato) -> decimal.Decimal:
    return sum(
        (
            saldo(db, d) or _CERO
            for d in descuentos_repo.listar_de_contrato(db, contrato.id)
            if d.tipo == "prestamo_empresa" and d.estado == "activo"
        ),
        _CERO,
    )


def cobrar_en_liquidacion(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    liquidacion_id: uuid.UUID,
    fecha: datetime.date,
    monto: decimal.Decimal,
) -> None:
    """Reparte `monto` entre los préstamos de la empresa del contrato, del
    más antiguo al más nuevo. Anular la liquidación devuelve el saldo."""
    restante = monto
    for descuento in descuentos_repo.listar_de_contrato(db, contrato.id):
        if restante <= _CERO:
            break
        if descuento.tipo != "prestamo_empresa" or descuento.estado != "activo":
            continue
        saldo_actual = saldo(db, descuento) or _CERO
        tomar = min(saldo_actual, restante)
        if tomar <= _CERO:
            continue
        descuentos_repo.crear_cuota(
            db,
            CuotaDescuento(
                empresa_id=empresa_id,
                descuento_id=descuento.id,
                liquidacion_id=liquidacion_id,
                fecha_cobro=fecha,
                monto=tomar,
                monto_programado=saldo_actual,
            ),
        )
        restante -= tomar

import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Ausencia, Contrato
from app.repositories import ausencias as ausencias_repo

# Catálogo verificado contra código-detrabajo.pdf (Art. 199/200/208) --
# ver FASE11-plan-ausencias.txt para el detalle de cada artículo. Este
# catálogo de _EXENTAS_SIEMPRE_VACACIONES/_SIEMPRE_DESCUENTA_VACACIONES/
# _SUJETA_UMBRAL_VACACIONES solo rige el descuento de VACACIONES
# (Art. 208 CT). El décimo NO usa este catálogo -- usa en cambio
# dias_sin_goce_de_salario() más abajo, un eje legal distinto ("¿se le
# paga el salario de esos días?" vs. "¿cuenta como antigüedad para
# ganar vacaciones?"). Ver CLAUDE.md sección 4.
TIPOS_AUSENCIA = frozenset(
    {
        "enfermedad_dentro_fondo",
        "enfermedad_excede_fondo",
        "embarazo",
        "riesgo_profesional",
        "huelga_legal",
        "licencia_sindical_o_estado",
        "licencia_autorizada_empleador",
        "arresto_o_prision_preventiva",
        "injustificada",
    }
)

# Vacaciones (Art. 199.4/199.5/199.7 CT): nunca se descuentan, sin
# importar la duración.
_EXENTAS_SIEMPRE_VACACIONES = {
    "enfermedad_dentro_fondo",
    "embarazo",
    "riesgo_profesional",
    "huelga_legal",
}
# Se descuenta completa desde el primer día (no es una "suspensión"
# de las del Art. 199, no aplica el umbral del Art. 208).
_SIEMPRE_DESCUENTA_VACACIONES = {"injustificada"}
# Art. 208: solo se descuenta el exceso sobre 15 días de la ausencia.
_SUJETA_UMBRAL_VACACIONES = {
    "enfermedad_excede_fondo",
    "licencia_sindical_o_estado",
    "licencia_autorizada_empleador",
    "arresto_o_prision_preventiva",
}
_UMBRAL_DIAS_VACACIONES = 15

# Goce de salario (¿se le paga esos días?), eje legal distinto del de
# vacaciones arriba -- confirmado por el usuario 2026-08-20: una
# ausencia injustificada (sin autorización) no genera derecho a
# salario ("a trabajo no realizado, no hay obligación de pago"). Los
# demás 8 tipos del catálogo quedan con goce de salario (sin
# descuento) hasta que el contador confirme su tratamiento individual
# -- Art. 199 los declara "suspensión sin responsabilidad para
# ninguna parte", que no necesariamente implica que el empleador deja
# de pagar, y enfermedad_dentro_fondo en particular SÍ tiene salario
# completo por texto expreso del Art. 200 CT.
_SIN_GOCE_SALARIO = {"injustificada"}

_CERO = decimal.Decimal("0")


def registrar_ausencia(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    tipo: str,
    fecha_desde: datetime.date,
    fecha_hasta: datetime.date,
    certificado_ref: str | None,
) -> Ausencia:
    if tipo not in TIPOS_AUSENCIA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Tipo de ausencia inválido: '{tipo}'. Valores válidos: {sorted(TIPOS_AUSENCIA)}.",
        )
    if fecha_hasta < fecha_desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "fecha_hasta no puede ser anterior a fecha_desde."
        )

    ausencia = ausencias_repo.crear(
        db, empresa_id, contrato.id, tipo, fecha_desde, fecha_hasta, certificado_ref
    )
    db.commit()
    # Sin db.refresh(): rompería RLS igual que en Fases 4/5/6/8/9 (SET
    # LOCAL app.empresa_actual no sobrevive al commit).
    return ausencia


def listar_ausencias(db: Session, contrato_id: uuid.UUID) -> list[Ausencia]:
    return ausencias_repo.listar_de_contrato(db, contrato_id)


def obtener_ausencia(db: Session, ausencia_id: uuid.UUID) -> Ausencia:
    ausencia = ausencias_repo.obtener(db, ausencia_id)
    if ausencia is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausencia no encontrada")
    return ausencia


def actualizar_documento_constancia(
    db: Session, ausencia: Ausencia, contenido: bytes, content_type: str, nombre_archivo: str
) -> Ausencia:
    """Documento de constancia (ej. certificado médico) de la ausencia,
    opcional. Se guarda en la propia tabla ausencias (bytea), mismo
    patrón que Empresa.logo y los documentos de empleado."""
    ausencia.documento_constancia = contenido
    ausencia.documento_constancia_content_type = content_type
    ausencia.documento_constancia_nombre_archivo = nombre_archivo
    db.commit()
    return ausencia


def _overlap_dias(
    a_desde: datetime.date,
    a_hasta: datetime.date,
    rango_desde: datetime.date,
    rango_hasta: datetime.date,
) -> decimal.Decimal:
    inicio = max(a_desde, rango_desde)
    fin = min(a_hasta, rango_hasta)
    if fin < inicio:
        return _CERO
    return decimal.Decimal((fin - inicio).days + 1)


def _dias_no_contables_de_ausencia(
    ausencia: Ausencia,
    rango_desde: datetime.date,
    rango_hasta: datetime.date,
) -> decimal.Decimal:
    if ausencia.tipo in _EXENTAS_SIEMPRE_VACACIONES:
        return _CERO
    if ausencia.tipo in _SIEMPRE_DESCUENTA_VACACIONES:
        return _overlap_dias(ausencia.fecha_desde, ausencia.fecha_hasta, rango_desde, rango_hasta)
    if ausencia.tipo in _SUJETA_UMBRAL_VACACIONES:
        # Art. 208 CT: "si el término de suspensión fuere superior a
        # quince días... se descontará". Se evalúa por cada ausencia
        # individual (los primeros 15 días de ESA ausencia quedan
        # protegidos, el resto se descuenta) -- simplificación
        # documentada: no se acumulan varias ausencias cortas dentro
        # de la misma ventana de 11 meses para ver si su SUMA supera
        # los 15 días: eso requeriría un diseño de ventanas móviles
        # más complejo, sin caso real todavía que lo exija. Ver
        # FASE11-plan-ausencias.txt.
        duracion_total = (ausencia.fecha_hasta - ausencia.fecha_desde).days + 1
        if duracion_total <= _UMBRAL_DIAS_VACACIONES:
            return _CERO
        fecha_inicio_excedente = ausencia.fecha_desde + datetime.timedelta(
            days=_UMBRAL_DIAS_VACACIONES
        )
        return _overlap_dias(fecha_inicio_excedente, ausencia.fecha_hasta, rango_desde, rango_hasta)

    return _CERO


def dias_no_contables(
    db: Session,
    contrato_id: uuid.UUID,
    fecha_inicio: datetime.date,
    fecha_fin: datetime.date,
) -> decimal.Decimal:
    """Días dentro de [fecha_inicio, fecha_fin] que NO cuentan como
    "día trabajado" para vacaciones, por causa de ausencias
    registradas (Art. 208 CT). Se resta directamente del total de días
    calculado en vacaciones_service."""
    if fecha_fin < fecha_inicio:
        return _CERO

    total = _CERO
    for ausencia in ausencias_repo.listar_de_contrato(db, contrato_id):
        total += _dias_no_contables_de_ausencia(ausencia, fecha_inicio, fecha_fin)
    return total


def dias_sin_goce_de_salario(
    db: Session,
    contrato_id: uuid.UUID,
    fecha_inicio: datetime.date,
    fecha_fin: datetime.date,
) -> decimal.Decimal:
    """Días dentro de [fecha_inicio, fecha_fin] en que el trabajador NO
    tiene derecho a salario por ausentarse sin autorización. Concepto
    distinto de dias_no_contables (esa rige solo el descuento de
    VACACIONES, Art. 208 CT, con su propio umbral y excepciones) -- no
    reutilizar, mezclaría dos reglas legales distintas. Se resta
    directamente del salario del período en planilla_service y de los
    días devengados en decimo_service."""
    if fecha_fin < fecha_inicio:
        return _CERO

    total = _CERO
    for ausencia in ausencias_repo.listar_de_contrato(db, contrato_id):
        if ausencia.tipo in _SIN_GOCE_SALARIO:
            total += _overlap_dias(ausencia.fecha_desde, ausencia.fecha_hasta, fecha_inicio, fecha_fin)
    return total

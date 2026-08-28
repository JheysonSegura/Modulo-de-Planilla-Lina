import datetime
import decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, RegistroHorasExtra
from app.repositories import historial_salarial as historial_repo
from app.repositories import horas_extra as horas_extra_repo
from app.repositories import tasas as tasas_repo

# Bandas de recargo del Art. 33 CT ya colapsadas como en CLAUDE.md
# sección 5: 'nocturna' incluye la prolongación de jornada mixta
# iniciada en período diurno, y 'prolongacion_nocturna' incluye la
# prolongación de mixta iniciada en período nocturno.
TIPO_HORA_A_TASA = {
    "diurna": "recargo_hextra_diurna",
    "nocturna": "recargo_hextra_nocturna",
    "prolongacion_nocturna": "recargo_hextra_prolongacion_nocturna",
}

# 'ordinario' no tiene recargo de día (factor 0, sin lookup).
TIPO_DIA_A_TASA = {
    "domingo_descanso": "recargo_dia_domingo_descanso",
    "feriado_duelo_nacional": "recargo_dia_feriado_duelo",
}

TASA_EXCESO_LIMITE = "recargo_exceso_limite_horas_extra"

LIMITE_DIARIO_HORAS = decimal.Decimal("3")
LIMITE_SEMANAL_HORAS = decimal.Decimal("9")

_CERO = decimal.Decimal("0")
_CENTAVO = decimal.Decimal("0.01")


def registrar_hora_extra(
    db: Session,
    empresa_id: uuid.UUID,
    contrato: Contrato,
    fecha: datetime.date,
    tipo_hora: str,
    tipo_dia: str,
    horas: decimal.Decimal,
    usuario_id: uuid.UUID | None = None,
    observaciones: str | None = None,
) -> RegistroHorasExtra:
    registro = RegistroHorasExtra(
        empresa_id=empresa_id,
        contrato_id=contrato.id,
        fecha=fecha,
        tipo_hora=tipo_hora,
        tipo_dia=tipo_dia,
        horas=horas,
        registrado_por_usuario_id=usuario_id,
        observaciones=observaciones,
    )
    horas_extra_repo.crear(db, registro)
    _recalcular_semana(db, contrato.id, fecha)
    db.commit()
    # Sin db.refresh(): rompería RLS (SET LOCAL app.empresa_actual no
    # sobrevive al commit; ver la misma nota en contratos_service.py) y
    # no hace falta -- _recalcular_semana ya deja el objeto con los
    # valores finales en Python antes del commit.
    return registro


def obtener_registro(db: Session, registro_id: uuid.UUID) -> RegistroHorasExtra:
    registro = horas_extra_repo.get(db, registro_id)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro de horas extra no encontrado")
    return registro


def listar_de_contrato(
    db: Session,
    contrato_id: uuid.UUID,
    desde: datetime.date | None = None,
    hasta: datetime.date | None = None,
) -> list[RegistroHorasExtra]:
    return horas_extra_repo.listar_de_contrato(db, contrato_id, desde, hasta)


def eliminar_registro(db: Session, registro: RegistroHorasExtra) -> None:
    if registro.aplicado:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede eliminar una hora extra que ya fue aplicada a una planilla.",
        )
    contrato_id = registro.contrato_id
    fecha = registro.fecha
    horas_extra_repo.eliminar(db, registro)
    _recalcular_semana(db, contrato_id, fecha)
    db.commit()


def _factor_obligatorio(db: Session, tipo_tasa: str, fecha: datetime.date) -> decimal.Decimal:
    tasa = tasas_repo.obtener_tasa_vigente(db, tipo_tasa, fecha)
    if tasa is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No hay una tasa vigente para '{tipo_tasa}' en la fecha {fecha.isoformat()}. "
            "Verifica el seed de tasas_vigentes (migración 0010).",
        )
    return tasa.tasa


def _recalcular_semana(db: Session, contrato_id: uuid.UUID, fecha: datetime.date) -> None:
    """Recorre TODOS los registros de la semana ISO de `fecha` para este
    contrato, en orden de fecha y luego de creación (FIFO), y recalcula
    la atribución dentro/exceso de los topes del Art. 36 CT (3h/día,
    9h/semana) junto con los montos en cascada. Se ejecuta completa cada
    vez que cambia un registro de la semana, para que una captura tardía
    de un día anterior reajuste correctamente lo que ya se había
    calculado para los días siguientes de la misma semana."""
    registros = horas_extra_repo.listar_de_semana_iso(db, contrato_id, fecha)

    horas_acumuladas_semana = _CERO
    horas_acumuladas_por_dia: dict[datetime.date, decimal.Decimal] = {}

    for registro in registros:
        horas_dia_previas = horas_acumuladas_por_dia.get(registro.fecha, _CERO)
        disponible_dia = max(_CERO, LIMITE_DIARIO_HORAS - horas_dia_previas)
        disponible_semana = max(_CERO, LIMITE_SEMANAL_HORAS - horas_acumuladas_semana)
        disponible = min(disponible_dia, disponible_semana)

        horas_dentro = min(registro.horas, disponible)
        horas_exceso = registro.horas - horas_dentro

        horas_acumuladas_por_dia[registro.fecha] = horas_dia_previas + registro.horas
        horas_acumuladas_semana += registro.horas

        salario_vigente = historial_repo.get_vigente_en_fecha(db, contrato_id, registro.fecha)
        if salario_vigente is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No hay un salario registrado para este contrato en la fecha "
                f"{registro.fecha.isoformat()} (es anterior al inicio del contrato).",
            )
        valor_hora_ordinaria = salario_vigente.salario_base / decimal.Decimal("30") / decimal.Decimal("8")

        factor_tipo_hora = _factor_obligatorio(
            db, TIPO_HORA_A_TASA[registro.tipo_hora], registro.fecha
        )

        tipo_dia_key = TIPO_DIA_A_TASA.get(registro.tipo_dia)
        factor_tipo_dia = (
            _factor_obligatorio(db, tipo_dia_key, registro.fecha)
            if tipo_dia_key is not None
            else _CERO
        )

        factor_exceso = (
            _factor_obligatorio(db, TASA_EXCESO_LIMITE, registro.fecha)
            if horas_exceso > _CERO
            else _CERO
        )

        # Cascada multiplicativa (nunca sumada, CLAUDE.md sección 5):
        # una hora extra nocturna en domingo es valor_hora * 1.5 * 1.5,
        # no valor_hora * 2.0.
        multiplicador_base = (1 + factor_tipo_hora) * (1 + factor_tipo_dia)
        monto_dentro = (horas_dentro * valor_hora_ordinaria * multiplicador_base).quantize(_CENTAVO)
        monto_exceso = (
            horas_exceso * valor_hora_ordinaria * multiplicador_base * (1 + factor_exceso)
        ).quantize(_CENTAVO)

        registro.horas_dentro_limite = horas_dentro
        registro.horas_exceso_limite = horas_exceso
        registro.valor_hora_ordinaria = valor_hora_ordinaria
        registro.factor_tipo_hora = factor_tipo_hora
        registro.factor_tipo_dia = factor_tipo_dia
        registro.factor_exceso_limite = factor_exceso
        registro.monto_dentro_limite = monto_dentro
        registro.monto_exceso_limite = monto_exceso
        registro.monto_calculado = monto_dentro + monto_exceso

    db.flush()

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, HistorialSalarial
from app.repositories import contratos as contratos_repo
from app.repositories import empleados as empleados_repo
from app.repositories import historial_salarial as historial_repo
from app.schemas.contratos import CambiarSalarioRequest, ContratoCreate, ContratoUpdate
from app.services.salario_minimo_service import validar_salario_minimo


def crear_contrato(
    db: Session, empresa_id: uuid.UUID, empleado_id: uuid.UUID, data: ContratoCreate
) -> Contrato:
    empleado = empleados_repo.get(db, empleado_id)
    if empleado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empleado no encontrado")

    # Salario mínimo vigente A LA FECHA DE INICIO del contrato, no al
    # salario mínimo actual (para poder registrar contratos retroactivos).
    validar_salario_minimo(db, data.fecha_inicio, data.salario_base)

    campos_contrato = data.model_dump(exclude={"salario_base"})
    contrato = Contrato(empresa_id=empresa_id, empleado_id=empleado_id, **campos_contrato)
    contratos_repo.crear(db, contrato)

    historial_repo.crear(
        db,
        HistorialSalarial(
            contrato_id=contrato.id,
            salario_base=data.salario_base,
            fecha_vigencia_desde=data.fecha_inicio,
            fecha_vigencia_hasta=None,
            motivo="ingreso",
        ),
    )
    db.commit()
    # Sin db.refresh(): rompería RLS (ver nota en empleados_service.py) y
    # no hace falta, ya viene poblado por RETURNING gracias al flush.
    return contrato


def obtener_contrato(db: Session, contrato_id: uuid.UUID) -> Contrato:
    contrato = contratos_repo.get(db, contrato_id)
    if contrato is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrato no encontrado")
    return contrato


def listar_contratos_de_empleado(db: Session, empleado_id: uuid.UUID) -> list[Contrato]:
    empleado = empleados_repo.get(db, empleado_id)
    if empleado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empleado no encontrado")
    return contratos_repo.listar_de_empleado(db, empleado_id)


def actualizar_contrato(db: Session, contrato: Contrato, data: ContratoUpdate) -> Contrato:
    cambios = data.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(contrato, campo, valor)
    db.commit()
    return contrato


def cambiar_salario(
    db: Session, contrato: Contrato, data: CambiarSalarioRequest
) -> HistorialSalarial:
    vigente = historial_repo.get_abierto(db, contrato.id)
    if vigente is None:
        # No debería pasar (todo contrato nace con un registro abierto en
        # crear_contrato); si pasa es un dato inconsistente, no algo para
        # adivinar en silencio.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El contrato no tiene un registro salarial vigente abierto en historial_salarial.",
        )
    if data.fecha_vigencia_desde <= vigente.fecha_vigencia_desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"La nueva fecha de vigencia ({data.fecha_vigencia_desde.isoformat()}) debe ser "
            f"posterior al inicio del salario vigente actual "
            f"({vigente.fecha_vigencia_desde.isoformat()}).",
        )

    # Salario mínimo vigente a la fecha en que empieza a regir el nuevo
    # salario (no al salario mínimo actual).
    validar_salario_minimo(db, data.fecha_vigencia_desde, data.salario_base)

    # No se sobrescribe: se cierra el registro vigente y se abre uno
    # nuevo, para que cualquier cálculo de un período pasado siga viendo
    # el salario que realmente regía en ese momento.
    vigente.fecha_vigencia_hasta = data.fecha_vigencia_desde - datetime.timedelta(days=1)

    nuevo = HistorialSalarial(
        contrato_id=contrato.id,
        salario_base=data.salario_base,
        fecha_vigencia_desde=data.fecha_vigencia_desde,
        fecha_vigencia_hasta=None,
        motivo=data.motivo,
    )
    historial_repo.crear(db, nuevo)
    db.commit()
    return nuevo


def salario_vigente_en_fecha(
    db: Session, contrato: Contrato, fecha: datetime.date
) -> HistorialSalarial:
    registro = historial_repo.get_vigente_en_fecha(db, contrato.id, fecha)
    if registro is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No hay un salario registrado para este contrato en la fecha {fecha.isoformat()}"
            " (es anterior al inicio del contrato).",
        )
    return registro


def listar_historial_salarial(db: Session, contrato: Contrato) -> list[HistorialSalarial]:
    return historial_repo.listar_de_contrato(db, contrato.id)

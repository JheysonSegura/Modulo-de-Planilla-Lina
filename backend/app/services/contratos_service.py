import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Contrato, HistorialCargo, HistorialSalarial
from app.repositories import contratos as contratos_repo
from app.repositories import empleados as empleados_repo
from app.repositories import empresas as empresas_repo
from app.repositories import historial_cargos as historial_cargos_repo
from app.repositories import historial_salarial as historial_repo
from app.schemas.contratos import (
    CambiarCargoRequest,
    CambiarSalarioRequest,
    ContratoCreate,
    ContratoUpdate,
)
from app.services import auditoria_service
from app.services.salario_minimo_service import validar_salario_minimo


def crear_contrato(
    db: Session, empresa_id: uuid.UUID, empleado_id: uuid.UUID, data: ContratoCreate
) -> Contrato:
    empleado = empleados_repo.get(db, empleado_id)
    if empleado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empleado no encontrado")

    # Salario mínimo vigente A LA FECHA DE INICIO del contrato, no al
    # salario mínimo actual (para poder registrar contratos retroactivos).
    # Se prorratea por jornada; si el contrato está marcado exento
    # (ej. pasantía formal, ver ContratoCreate) no se valida en absoluto.
    if not data.exento_salario_minimo:
        empresa = empresas_repo.get(db, empresa_id)
        validar_salario_minimo(
            db, empresa, data.fecha_inicio, data.salario_base, data.jornada_horas_semana
        )

    campos_contrato = data.model_dump(exclude={"salario_base"})
    contrato = Contrato(empresa_id=empresa_id, empleado_id=empleado_id, **campos_contrato)
    contratos_repo.crear(db, contrato)

    historial_repo.crear(
        db,
        HistorialSalarial(
            empresa_id=empresa_id,
            contrato_id=contrato.id,
            salario_base=data.salario_base,
            fecha_vigencia_desde=data.fecha_inicio,
            fecha_vigencia_hasta=None,
            motivo="ingreso",
        ),
    )
    historial_cargos_repo.crear(
        db,
        HistorialCargo(
            empresa_id=empresa_id,
            contrato_id=contrato.id,
            cargo=data.cargo,
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
    db: Session, contrato: Contrato, data: CambiarSalarioRequest, usuario_id: uuid.UUID
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

    # El salario de un contrato vigente nunca puede bajar (irrenunciabilidad
    # de derechos laborales, confirmado explícitamente por el usuario --
    # ver CLAUDE.md). Para pagarle menos a alguien hay que liquidar el
    # contrato (POST /contratos/{id}/liquidacion) y firmar uno nuevo.
    if data.salario_base <= vigente.salario_base:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El nuevo salario (${data.salario_base}) debe ser mayor al salario vigente "
            f"(${vigente.salario_base}). El salario de un contrato vigente no se puede bajar "
            "-- para pagar menos hay que liquidar el contrato y crear uno nuevo.",
        )

    # Salario mínimo vigente a la fecha en que empieza a regir el nuevo
    # salario (no al salario mínimo actual). Respeta la misma exención
    # del contrato (no se puede "esquivar" el flag cambiando el salario).
    if not contrato.exento_salario_minimo:
        empresa = empresas_repo.get(db, contrato.empresa_id)
        validar_salario_minimo(
            db,
            empresa,
            data.fecha_vigencia_desde,
            data.salario_base,
            contrato.jornada_horas_semana,
        )

    # No se sobrescribe: se cierra el registro vigente y se abre uno
    # nuevo, para que cualquier cálculo de un período pasado siga viendo
    # el salario que realmente regía en ese momento.
    vigente.fecha_vigencia_hasta = data.fecha_vigencia_desde - datetime.timedelta(days=1)

    salario_anterior = vigente.salario_base
    fecha_desde_anterior = vigente.fecha_vigencia_desde

    nuevo = HistorialSalarial(
        empresa_id=contrato.empresa_id,
        contrato_id=contrato.id,
        salario_base=data.salario_base,
        fecha_vigencia_desde=data.fecha_vigencia_desde,
        fecha_vigencia_hasta=None,
        motivo=data.motivo,
    )
    historial_repo.crear(db, nuevo)

    auditoria_service.registrar(
        db,
        contrato.empresa_id,
        usuario_id,
        "contratos",
        contrato.id,
        "cambio_salario",
        empleado_id=contrato.empleado_id,
        datos_anteriores={
            "salario_base": str(salario_anterior),
            "fecha_vigencia_desde": fecha_desde_anterior.isoformat(),
        },
        datos_nuevos={
            "salario_base": str(nuevo.salario_base),
            "fecha_vigencia_desde": nuevo.fecha_vigencia_desde.isoformat(),
            "motivo": nuevo.motivo,
        },
    )

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


def cambiar_cargo(
    db: Session, contrato: Contrato, data: CambiarCargoRequest, usuario_id: uuid.UUID
) -> HistorialCargo:
    vigente = historial_cargos_repo.get_abierto(db, contrato.id)
    if vigente is None:
        # No debería pasar (todo contrato nace con un registro abierto en
        # crear_contrato); si pasa es un dato inconsistente, no algo para
        # adivinar en silencio.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El contrato no tiene un registro de cargo vigente abierto en historial_cargos.",
        )
    if data.fecha_vigencia_desde <= vigente.fecha_vigencia_desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"La nueva fecha de vigencia ({data.fecha_vigencia_desde.isoformat()}) debe ser "
            f"posterior al inicio del cargo vigente actual "
            f"({vigente.fecha_vigencia_desde.isoformat()}).",
        )

    if data.cargo == vigente.cargo:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El nuevo cargo debe ser distinto del cargo vigente ({vigente.cargo}).",
        )

    # No se sobrescribe: se cierra el registro vigente y se abre uno
    # nuevo, para poder saber siempre cuánto tiempo se estuvo en cada
    # cargo (un cambio de puesto es una adenda al mismo contrato, nunca
    # un contrato nuevo).
    vigente.fecha_vigencia_hasta = data.fecha_vigencia_desde - datetime.timedelta(days=1)

    cargo_anterior = vigente.cargo
    fecha_desde_anterior = vigente.fecha_vigencia_desde

    nuevo = HistorialCargo(
        empresa_id=contrato.empresa_id,
        contrato_id=contrato.id,
        cargo=data.cargo,
        fecha_vigencia_desde=data.fecha_vigencia_desde,
        fecha_vigencia_hasta=None,
        motivo=data.motivo,
    )
    historial_cargos_repo.crear(db, nuevo)

    # contratos.cargo queda como el "cargo actual" denormalizado -- así
    # los recibos/exportaciones que ya lo leen directo no necesitan
    # cambiar, la fuente de verdad histórica vive en historial_cargos.
    contrato.cargo = data.cargo

    auditoria_service.registrar(
        db,
        contrato.empresa_id,
        usuario_id,
        "contratos",
        contrato.id,
        "cambio_cargo",
        empleado_id=contrato.empleado_id,
        datos_anteriores={
            "cargo": cargo_anterior,
            "fecha_vigencia_desde": fecha_desde_anterior.isoformat(),
        },
        datos_nuevos={
            "cargo": nuevo.cargo,
            "fecha_vigencia_desde": nuevo.fecha_vigencia_desde.isoformat(),
            "motivo": nuevo.motivo,
        },
    )

    db.commit()
    return nuevo


def listar_historial_cargos(db: Session, contrato: Contrato) -> list[HistorialCargo]:
    return historial_cargos_repo.listar_de_contrato(db, contrato.id)

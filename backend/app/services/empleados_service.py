import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Empleado
from app.repositories import empleados as empleados_repo
from app.schemas.empleados import EmpleadoCreate, EmpleadoUpdate


def crear_empleado(db: Session, empresa_id: uuid.UUID, data: EmpleadoCreate) -> Empleado:
    empleado = Empleado(empresa_id=empresa_id, **data.model_dump())
    empleados_repo.crear(db, empleado)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un empleado con esa identificación en esta empresa",
        ) from exc
    # NO db.refresh() aquí: forzaría un SELECT en una transacción nueva,
    # donde app.empresa_actual (SET LOCAL en get_db_rls) ya no está fijado
    # -> la política RLS fallaría. La sesión usa expire_on_commit=False,
    # así que los valores generados por el server (id, created_at, etc.)
    # ya quedaron cargados en `empleado` vía RETURNING durante el commit.
    return empleado


def obtener_empleado(db: Session, empleado_id: uuid.UUID) -> Empleado:
    empleado = empleados_repo.get(db, empleado_id)
    if empleado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empleado no encontrado")
    return empleado


def listar_empleados(db: Session) -> list[Empleado]:
    return empleados_repo.listar(db)


def actualizar_empleado(db: Session, empleado: Empleado, data: EmpleadoUpdate) -> Empleado:
    cambios = data.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(empleado, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un empleado con esa identificación en esta empresa",
        ) from exc
    return empleado

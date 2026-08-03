import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Empleado


def crear(db: Session, empleado: Empleado) -> Empleado:
    db.add(empleado)
    db.flush()
    return empleado


def get(db: Session, empleado_id: uuid.UUID) -> Empleado | None:
    # db.get() hace un SELECT por PK; si RLS filtra la fila (otra empresa),
    # simplemente no la trae -> se comporta como "no existe" para quien no
    # tiene acceso, sin necesidad de ningún chequeo extra en el código.
    return db.get(Empleado, empleado_id)


def listar(db: Session) -> list[Empleado]:
    return list(db.execute(select(Empleado).order_by(Empleado.nombre_completo)).scalars().all())

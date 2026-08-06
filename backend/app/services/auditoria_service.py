import uuid

from sqlalchemy.orm import Session

from app.models import AuditoriaCambio
from app.repositories import auditoria as auditoria_repo


def registrar(
    db: Session,
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID | None,
    tabla_afectada: str,
    registro_id: uuid.UUID,
    accion: str,
    empleado_id: uuid.UUID | None = None,
    datos_anteriores: dict | None = None,
    datos_nuevos: dict | None = None,
) -> AuditoriaCambio:
    """Registra un evento de auditoría. Se llama SIEMPRE dentro de la
    misma transacción que el cambio que audita (antes del db.commit()
    del servicio que lo invoca), para que ambos queden atómicos: si el
    cambio falla, no queda un registro de auditoría huérfano, y
    viceversa."""
    return auditoria_repo.crear(
        db,
        AuditoriaCambio(
            empresa_id=empresa_id,
            empleado_id=empleado_id,
            usuario_id=usuario_id,
            tabla_afectada=tabla_afectada,
            registro_id=registro_id,
            accion=accion,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
        ),
    )


def listar(
    db: Session,
    empleado_id: uuid.UUID | None = None,
    tabla_afectada: str | None = None,
    accion: str | None = None,
) -> list[AuditoriaCambio]:
    return auditoria_repo.listar(db, empleado_id, tabla_afectada, accion)

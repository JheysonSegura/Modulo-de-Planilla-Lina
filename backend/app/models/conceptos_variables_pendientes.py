import datetime
import decimal
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ConceptoVariablePendiente(Base):
    """Captura previa de bonos/comisiones/descuentos puntuales por
    contrato, antes de que exista una planilla. El motor de planilla
    (app/services/planilla_service.py) los recoge por rango de fecha,
    los copia a conceptos_variables ligados al movimiento generado, y
    marca aplicado=True para que no se dupliquen en una corrida futura."""

    __tablename__ = "conceptos_variables_pendientes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    fecha: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    aplicado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    movimiento_planilla_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movimientos_planilla.id")
    )
    registrado_por_usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

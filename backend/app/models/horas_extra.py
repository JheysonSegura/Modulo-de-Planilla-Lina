import datetime
import decimal
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RegistroHorasExtra(Base):
    """Detalle auditable de horas extra por contrato/día. Los campos de
    factor_*/monto_* son snapshots recalculados por
    horas_extra_service._recalcular_semana cada vez que cambia algún
    registro de la misma semana ISO (ver CLAUDE.md sección 6)."""

    __tablename__ = "registro_horas_extra"

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
    tipo_hora: Mapped[str] = mapped_column(String(30), nullable=False)
    tipo_dia: Mapped[str] = mapped_column(String(30), nullable=False, server_default="ordinario")
    horas: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    horas_dentro_limite: Mapped[decimal.Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    horas_exceso_limite: Mapped[decimal.Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )
    valor_hora_ordinaria: Mapped[decimal.Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0"
    )
    factor_tipo_hora: Mapped[decimal.Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    factor_tipo_dia: Mapped[decimal.Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    factor_exceso_limite: Mapped[decimal.Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    monto_dentro_limite: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    monto_exceso_limite: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    monto_calculado: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    registrado_por_usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    observaciones: Mapped[str | None] = mapped_column(Text)
    # No se puede borrar una vez aplicada (ver horas_extra_service.py::
    # eliminar_registro) -- mismo patrón que ConceptoVariablePendiente.
    aplicado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    movimiento_planilla_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movimientos_planilla.id")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

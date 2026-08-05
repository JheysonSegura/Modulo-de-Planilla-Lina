import datetime
import decimal
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Liquidacion(Base):
    __tablename__ = "liquidaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    fecha_terminacion: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    motivo: Mapped[str] = mapped_column(String(50), nullable=False)
    salario_pendiente: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    decimo_proporcional: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    vacaciones_pendientes: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    preaviso: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    indemnizacion: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    prima_antiguedad: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    otras_deducciones: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    monto_total: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="borrador")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

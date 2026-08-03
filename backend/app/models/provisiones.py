import datetime
import decimal
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ProvisionDecimo(Base):
    __tablename__ = "provisiones_decimo"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    cuatrimestre: Mapped[str] = mapped_column(String(20), nullable=False)
    anio: Mapped[int] = mapped_column(nullable=False)
    monto_acumulado: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    fecha_pago_programada: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    pagado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fecha_pago_real: Mapped[datetime.date | None] = mapped_column(Date)
    movimiento_planilla_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movimientos_planilla.id")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )


class ProvisionVacaciones(Base):
    __tablename__ = "provisiones_vacaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    fecha_inicio_periodo: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dias_acumulados: Mapped[decimal.Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="0"
    )
    dias_gozados: Mapped[decimal.Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="0"
    )
    monto_provisionado: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="abierto")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

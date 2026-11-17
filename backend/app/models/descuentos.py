import datetime
import decimal
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class DescuentoRecurrente(Base):
    """Préstamo o descuento que se cobra en cada fecha de cobro hasta
    saldarse (o, si no tiene monto_total, hasta que alguien lo cierre).
    Art. 161 CT -- ver PLAN-descuentos-prestamos.md y descuentos_service.
    El saldo no se guarda: se calcula desde cuotas_descuento."""

    __tablename__ = "descuentos_recurrentes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    acreedor: Mapped[str] = mapped_column(String(150), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(100))
    monto_total: Mapped[decimal.Decimal | None] = mapped_column(Numeric(12, 2))
    plazo_meses: Mapped[int | None] = mapped_column(Integer)
    frecuencia: Mapped[str] = mapped_column(String(10), nullable=False)
    numero_cuotas: Mapped[int | None] = mapped_column(Integer)
    cuota: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activo")
    fecha_cierre: Mapped[datetime.date | None] = mapped_column(Date)
    motivo_cierre: Mapped[str | None] = mapped_column(Text)
    observacion: Mapped[str | None] = mapped_column(Text)
    documento: Mapped[bytes | None] = mapped_column(LargeBinary)
    documento_content_type: Mapped[str | None] = mapped_column(String(50))
    documento_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    registrado_por_usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )


class CuotaDescuento(Base):
    """Un cobro efectivo de un descuento: en un movimiento de planilla
    (quincena/mes o vacaciones) o en una liquidación."""

    __tablename__ = "cuotas_descuento"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    descuento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("descuentos_recurrentes.id"), nullable=False
    )
    movimiento_planilla_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movimientos_planilla.id")
    )
    liquidacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("liquidaciones.id")
    )
    fecha_cobro: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    monto: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_programado: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

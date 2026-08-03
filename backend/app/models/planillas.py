import datetime
import decimal
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Planilla(Base):
    __tablename__ = "planillas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    periodo_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    periodo_fin: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_pago: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="borrador")
    procesada_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

    movimientos: Mapped[list["MovimientoPlanilla"]] = relationship(back_populates="planilla")


class MovimientoPlanilla(Base):
    __tablename__ = "movimientos_planilla"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    planilla_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planillas.id"), nullable=False
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    salario_base_periodo: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    salario_bruto: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    css_empleado: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    css_patronal: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    seguro_educativo_empleado: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    seguro_educativo_patronal: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    riesgo_profesional_patronal: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    isr_retenido: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    otras_deducciones: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    salario_neto: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    planilla: Mapped["Planilla"] = relationship(back_populates="movimientos")
    conceptos_variables: Mapped[list["ConceptoVariable"]] = relationship(
        back_populates="movimiento_planilla"
    )


class ConceptoVariable(Base):
    """Horas extra, bonos, préstamos, tardanzas, etc. Tabla flexible
    para no alterar movimientos_planilla cada vez que aparece un nuevo
    tipo de ingreso/deducción."""

    __tablename__ = "conceptos_variables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    movimiento_planilla_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movimientos_planilla.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    movimiento_planilla: Mapped["MovimientoPlanilla"] = relationship(
        back_populates="conceptos_variables"
    )

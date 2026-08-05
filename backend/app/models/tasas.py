import datetime
import decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class TasaVigente(Base):
    """Tasas nacionales (CSS, Seguro Educativo, décimo) con vigencia por
    fecha. Se comparten entre todas las empresas, nunca se duplican."""

    __tablename__ = "tasas_vigentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_tasa: Mapped[str] = mapped_column(String(50), nullable=False)
    tasa: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)
    fuente_legal: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TasaRiesgoProfesional(Base):
    """La tasa depende de la clase de riesgo de la actividad económica
    de la empresa (I a V según CSS), no es un valor único."""

    __tablename__ = "tasas_riesgo_profesional"

    id: Mapped[int] = mapped_column(primary_key=True)
    clase_riesgo: Mapped[str] = mapped_column(String(20), nullable=False)
    tasa: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TramoIsr(Base):
    """Tabla progresiva de ISR, con vigencia por fecha porque el MEF
    puede modificarla."""

    __tablename__ = "tramos_isr"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)
    monto_desde: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_hasta: Mapped[decimal.Decimal | None] = mapped_column(Numeric(12, 2))
    tasa_marginal: Mapped[decimal.Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    impuesto_base: Mapped[decimal.Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ParametroIsr(Base):
    """Parámetro nacional (no por empresa, CLAUDE.md sección 2) que
    decide si el décimo tercer mes se integra a la base gravable del
    ISR o se trata como exento. Deliberadamente sin ninguna fila
    sembrada hasta que el contador lo confirme -- ver migración
    0014_parametros_isr y app/services/planilla_service.py."""

    __tablename__ = "parametros_isr"

    id: Mapped[int] = mapped_column(primary_key=True)
    decimo_incluido_en_base_gravable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)
    fuente_legal: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SalarioMinimoVigente(Base):
    """Decreto Ejecutivo N.13, varía por región/actividad."""

    __tablename__ = "salario_minimo_vigente"

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    actividad: Mapped[str | None] = mapped_column(String(150))
    # Declaración manual (no calculada) de si la fila aplica a pequeña o
    # gran empresa -- el umbral de empleados que distingue una de otra
    # varía por sector (Decreto Ejecutivo N.13). NULL si la actividad no
    # se divide por tamaño.
    tamano_empresa: Mapped[str | None] = mapped_column(String(50))
    monto_hora: Mapped[decimal.Decimal | None] = mapped_column(Numeric(10, 4))
    monto_mensual: Mapped[decimal.Decimal | None] = mapped_column(Numeric(12, 2))
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(Date)
    decreto_ref: Mapped[str | None] = mapped_column(String(100))

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Ausencia(Base):
    """Registro de una ausencia/incapacidad de un contrato (Fase 11).
    Rango cerrado (fecha_desde/fecha_hasta siempre conocidas) -- a
    diferencia de historial_salarial, una ausencia no se captura
    "abierta". Ver FASE11-plan-ausencias.txt para el catálogo de
    `tipo` y su efecto sobre décimo/vacaciones (app.services.ausencias_service)."""

    __tablename__ = "ausencias"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha_desde: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_hasta: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    certificado_ref: Mapped[str | None] = mapped_column(String(100))
    documento_constancia: Mapped[bytes | None] = mapped_column(LargeBinary)
    documento_constancia_content_type: Mapped[str | None] = mapped_column(String(50))
    documento_constancia_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

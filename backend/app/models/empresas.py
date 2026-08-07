import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    razon_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(200))
    ruc: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    dv: Mapped[str | None] = mapped_column(String(5))
    numero_patronal_css: Mapped[str | None] = mapped_column(String(30))
    clase_riesgo: Mapped[str | None] = mapped_column(String(20))
    # Región y actividad económica del Decreto Ejecutivo N.13: de qué fila
    # de salario_minimo_vigente depende esta empresa cuando hay más de una
    # vigente a la vez (ver app/services/salario_minimo_service.py).
    region: Mapped[str | None] = mapped_column(String(100))
    actividad_economica: Mapped[str | None] = mapped_column(String(150))
    # Declaración manual de pequeña/gran empresa (Decreto Ejecutivo N.13);
    # el sistema no cuenta empleados para inferirlo, ver salario_minimo_service.
    tamano_empresa: Mapped[str | None] = mapped_column(String(50))
    direccion: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(String(30))
    email_contacto: Mapped[str | None] = mapped_column(String(150))
    representante_legal: Mapped[str | None] = mapped_column(String(200))
    # Fase 16: membrete para recibos y reportes (junto con ruc/dv/direccion/
    # telefono, que ya existían pero no se usaban en ningún documento).
    logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_content_type: Mapped[str | None] = mapped_column(String(50))
    moneda: Mapped[str] = mapped_column(String(10), nullable=False, server_default="USD")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuarios_empresas: Mapped[list["UsuarioEmpresa"]] = relationship(back_populates="empresa")


class UsuarioEmpresa(Base):
    """Relación muchos a muchos usuarios<->empresas, con rol por empresa.
    Permite que un mismo contador administre varias empresas con roles
    distintos en cada una."""

    __tablename__ = "usuarios_empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False
    )
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="usuarios_empresas")

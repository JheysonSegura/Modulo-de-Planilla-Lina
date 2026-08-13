import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Usuario(Base):
    """Usuario del sistema, desacoplado de 'empleados'. El rol es por
    empresa (ver UsuarioEmpresa), no global."""

    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Bandera GLOBAL (no un rol por empresa) -- ver CLAUDE.md. Solo se
    # otorga con scripts/otorgar_superadmin.py, nunca desde la app.
    es_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Permiso delegado, también GLOBAL -- a diferencia de es_superadmin,
    # SÍ se togglea desde la app, pero solo por un superadmin (GET/PATCH
    # /usuarios). Deja crear empresas (POST /empresas) sin el resto de
    # los poderes de superadmin.
    puede_crear_empresas: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    ultimo_login: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

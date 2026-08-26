import datetime
import decimal
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Empleado(Base):
    __tablename__ = "empleados"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "tipo_identificacion", "identificacion",
            name="uq_empleados_empresa_identificacion",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    tipo_identificacion: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="cedula"
    )
    identificacion: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_nacimiento: Mapped[datetime.date | None] = mapped_column(Date)
    nacionalidad: Mapped[str | None] = mapped_column(String(50))
    sexo: Mapped[str | None] = mapped_column(String(20))
    email_personal: Mapped[str | None] = mapped_column(String(150))
    codigo_pais: Mapped[str | None] = mapped_column(String(5))
    telefono: Mapped[str | None] = mapped_column(String(30))
    direccion: Mapped[str | None] = mapped_column(Text)
    numero_seguro_social: Mapped[str | None] = mapped_column(String(30))
    padece_enfermedad: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    detalle_enfermedad: Mapped[str | None] = mapped_column(Text)
    # Documentos personales (Fase 17): mismo patrón que Empresa.logo -- bytea
    # en la propia tabla, servido aparte por endpoint dedicado, nunca inline
    # en EmpleadoOut.
    documento_identificacion: Mapped[bytes | None] = mapped_column(LargeBinary)
    documento_identificacion_content_type: Mapped[str | None] = mapped_column(String(50))
    documento_identificacion_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    documento_certificado_medico: Mapped[bytes | None] = mapped_column(LargeBinary)
    documento_certificado_medico_content_type: Mapped[str | None] = mapped_column(String(50))
    documento_certificado_medico_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activo")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

    contratos: Mapped[list["Contrato"]] = relationship(back_populates="empleado")


class Contrato(Base):
    __tablename__ = "contratos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    empleado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empleados.id"), nullable=False
    )
    tipo_contrato: Mapped[str] = mapped_column(String(30), nullable=False)
    cargo: Mapped[str] = mapped_column(String(150), nullable=False)
    departamento: Mapped[str | None] = mapped_column(String(150))
    fecha_inicio: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin_pactada: Mapped[datetime.date | None] = mapped_column(Date)
    fecha_fin_real: Mapped[datetime.date | None] = mapped_column(Date)
    jornada_horas_semana: Mapped[decimal.Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="48"
    )
    periodicidad_pago: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="quincenal"
    )
    fecha_registro_mitradel: Mapped[datetime.date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="vigente")
    motivo_terminacion: Mapped[str | None] = mapped_column(String(50))
    # Excepción explícita y auditable a la validación de salario mínimo
    # (ej. pasantía formal). Nunca se infiere de tipo_contrato: el
    # tratamiento legal de estos casos no está confirmado con el contador
    # (ver migración 0009_exencion_salario_minimo). El caso de medio
    # tiempo NO usa este flag, se prorratea por jornada_horas_semana.
    exento_salario_minimo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    motivo_exencion_salario_minimo: Mapped[str | None] = mapped_column(String(200))
    # Art. 222 CT: el aviso de renuncia exigido es de 15 días, salvo
    # "trabajador técnico", que requiere 2 meses -- usado en
    # liquidaciones_service para la penalidad por renuncia sin aviso
    # (Fase 13).
    es_tecnico: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

    empleado: Mapped["Empleado"] = relationship(back_populates="contratos")
    historial_salarial: Mapped[list["HistorialSalarial"]] = relationship(
        back_populates="contrato"
    )


class HistorialSalarial(Base):
    """Separado de 'contratos' porque el salario puede cambiar sin que
    cambie el contrato, y el ISR + la cláusula de variación >30% de la
    Ley 462 necesitan ver esta historia completa."""

    __tablename__ = "historial_salarial"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    contrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contratos.id"), nullable=False
    )
    salario_base: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_vigencia_desde: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_vigencia_hasta: Mapped[datetime.date | None] = mapped_column(Date)
    motivo: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Auditoría de seguridad 2026-08-25 (hallazgo M2): ver nota en
    # MovimientoPlanilla.empresa_id -- misma denormalización, mismo motivo.
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id")
    )

    contrato: Mapped["Contrato"] = relationship(back_populates="historial_salarial")

-- =====================================================================
-- ESQUEMA DE BASE DE DATOS - APP DE NÓMINA/PLANILLA PANAMÁ
-- Motor: PostgreSQL 15+
-- Diseñado para: FastAPI backend, standalone app con auth propia,
-- preparado para futura integración como módulo de ERP.
-- =====================================================================

-- Extensión recomendada para UUIDs (mejor que serial si luego vas a
-- sincronizar IDs con un ERP externo, evita colisiones de secuencias)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================
-- 1. AUTENTICACIÓN Y USUARIOS DEL SISTEMA (desacoplado de "empleados")
-- =====================================================================

CREATE TABLE roles (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) UNIQUE NOT NULL,   -- 'admin', 'contador', 'consulta'
    descripcion     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usuarios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(200) NOT NULL,
    rol_id          INTEGER NOT NULL REFERENCES roles(id),
    activo          BOOLEAN NOT NULL DEFAULT true,
    ultimo_login    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 2. EMPLEADOS Y CONTRATOS
-- =====================================================================

CREATE TABLE empleados (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo_identificacion VARCHAR(20) NOT NULL DEFAULT 'cedula', -- 'cedula', 'pasaporte'
    identificacion      VARCHAR(30) NOT NULL,
    nombre_completo     VARCHAR(200) NOT NULL,
    fecha_nacimiento    DATE,
    fecha_nacionalidad  VARCHAR(50),               -- relevante por afiliación migrante (Ley 462)
    email_personal      VARCHAR(150),
    telefono            VARCHAR(30),
    direccion           TEXT,
    numero_seguro_social VARCHAR(30),               -- asignado por la CSS al afiliar
    estado              VARCHAR(20) NOT NULL DEFAULT 'activo', -- 'activo','inactivo'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tipo_identificacion, identificacion)
);

CREATE TABLE contratos (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empleado_id             UUID NOT NULL REFERENCES empleados(id),
    tipo_contrato           VARCHAR(30) NOT NULL,   -- 'indefinido','definido','obra_determinada'
    cargo                   VARCHAR(150) NOT NULL,
    departamento            VARCHAR(150),
    fecha_inicio            DATE NOT NULL,          -- "hora 0:00" del inicio de la relación laboral
    fecha_fin_pactada       DATE,                   -- solo para contratos definidos/por obra
    fecha_fin_real          DATE,                   -- se llena al terminar la relación laboral
    jornada_horas_semana    NUMERIC(5,2) NOT NULL DEFAULT 48,
    periodicidad_pago       VARCHAR(20) NOT NULL DEFAULT 'quincenal', -- 'quincenal','mensual'
    fecha_registro_mitradel DATE,                   -- registro dentro de los 15 días de firmado
    estado                  VARCHAR(20) NOT NULL DEFAULT 'vigente',  -- 'vigente','terminado'
    motivo_terminacion      VARCHAR(50),             -- 'renuncia','despido_justificado',
                                                      -- 'despido_injustificado','mutuo_acuerdo', etc.
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contratos_empleado ON contratos(empleado_id);
CREATE INDEX idx_contratos_estado ON contratos(estado);

-- Historial salarial: separado de "contratos" porque el salario puede
-- cambiar sin que cambie el contrato, y el ISR + la cláusula de
-- variación >30% de la Ley 462 necesitan ver esta historia completa.
CREATE TABLE historial_salarial (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contrato_id         UUID NOT NULL REFERENCES contratos(id),
    salario_base        NUMERIC(12,2) NOT NULL,
    fecha_vigencia_desde DATE NOT NULL,
    fecha_vigencia_hasta DATE,                      -- NULL = vigente actualmente
    motivo              VARCHAR(100),                -- 'ingreso','ajuste_anual','promocion', etc.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_historial_salarial_contrato ON historial_salarial(contrato_id);

-- =====================================================================
-- 3. TASAS Y PARÁMETROS LEGALES VIGENTES POR FECHA
-- (CSS, Seguro Educativo, décimo mes, riesgos profesionales)
-- =====================================================================

CREATE TABLE tasas_vigentes (
    id              SERIAL PRIMARY KEY,
    tipo_tasa       VARCHAR(50) NOT NULL,   -- 'css_empleado','css_patronal',
                                             -- 'seguro_educativo_empleado','seguro_educativo_patronal',
                                             -- 'decimo_empleado','decimo_patronal'
    tasa            NUMERIC(6,4) NOT NULL,  -- ej. 0.1325 para 13.25%
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE,                   -- NULL = vigente indefinidamente
    fuente_legal    VARCHAR(150),           -- ej. 'Ley 462 de 2025, Art. 84'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasas_tipo_fecha ON tasas_vigentes(tipo_tasa, fecha_inicio);

-- Riesgos profesionales: la tasa depende de la clase de riesgo de la
-- actividad económica de la empresa, no es un valor único.
CREATE TABLE tasas_riesgo_profesional (
    id              SERIAL PRIMARY KEY,
    clase_riesgo    VARCHAR(20) NOT NULL,   -- I, II, III, IV, V (según CSS)
    tasa            NUMERIC(6,4) NOT NULL,
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tramos de ISR (tabla progresiva), con vigencia por fecha porque
-- el MEF puede modificarla.
CREATE TABLE tramos_isr (
    id              SERIAL PRIMARY KEY,
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE,
    monto_desde     NUMERIC(12,2) NOT NULL,
    monto_hasta     NUMERIC(12,2),           -- NULL = sin tope superior
    tasa_marginal   NUMERIC(6,4) NOT NULL,   -- tasa aplicable al excedente del tramo
    impuesto_base   NUMERIC(12,2) NOT NULL DEFAULT 0, -- acumulado de tramos anteriores
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tramos_isr_fecha ON tramos_isr(fecha_inicio);

-- Salario mínimo vigente (Decreto Ejecutivo, varía por región/actividad)
CREATE TABLE salario_minimo_vigente (
    id              SERIAL PRIMARY KEY,
    region          VARCHAR(100) NOT NULL,   -- ej. 'Región 1', 'Región 2' según decreto
    actividad       VARCHAR(150),            -- opcional, si el decreto distingue por sector
    monto_hora      NUMERIC(10,4),
    monto_mensual   NUMERIC(12,2),
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE,
    decreto_ref     VARCHAR(100)             -- ej. 'Decreto Ejecutivo N.13'
);

-- =====================================================================
-- 4. PLANILLAS (corridas de nómina) Y MOVIMIENTOS
-- =====================================================================

CREATE TABLE planillas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tipo            VARCHAR(20) NOT NULL,   -- 'quincenal','mensual','decimo_tercer_mes'
    periodo_inicio  DATE NOT NULL,
    periodo_fin     DATE NOT NULL,
    fecha_pago      DATE NOT NULL,
    estado          VARCHAR(20) NOT NULL DEFAULT 'borrador', -- 'borrador','procesada','pagada','anulada'
    procesada_por   UUID REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE movimientos_planilla (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    planilla_id                 UUID NOT NULL REFERENCES planillas(id),
    contrato_id                 UUID NOT NULL REFERENCES contratos(id),
    salario_base_periodo        NUMERIC(12,2) NOT NULL,
    salario_bruto               NUMERIC(12,2) NOT NULL,  -- base + variables (ingresos)
    css_empleado                NUMERIC(12,2) NOT NULL,
    css_patronal                NUMERIC(12,2) NOT NULL,
    seguro_educativo_empleado   NUMERIC(12,2) NOT NULL,
    seguro_educativo_patronal   NUMERIC(12,2) NOT NULL,
    riesgo_profesional_patronal NUMERIC(12,2) NOT NULL DEFAULT 0,
    isr_retenido                NUMERIC(12,2) NOT NULL DEFAULT 0,
    otras_deducciones           NUMERIC(12,2) NOT NULL DEFAULT 0,
    salario_neto                NUMERIC(12,2) NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_movimientos_planilla ON movimientos_planilla(planilla_id);
CREATE INDEX idx_movimientos_contrato ON movimientos_planilla(contrato_id);

-- Conceptos variables: horas extra, bonos, préstamos, tardanzas, etc.
-- Tabla flexible para no tener que alterar movimientos_planilla cada
-- vez que aparece un nuevo tipo de ingreso/deducción.
CREATE TABLE conceptos_variables (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    movimiento_planilla_id  UUID NOT NULL REFERENCES movimientos_planilla(id),
    tipo                    VARCHAR(20) NOT NULL,  -- 'ingreso','deduccion'
    codigo                  VARCHAR(50) NOT NULL,  -- 'hora_extra','bono','prestamo','tardanza'
    descripcion             TEXT,
    monto                   NUMERIC(12,2) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conceptos_movimiento ON conceptos_variables(movimiento_planilla_id);

-- =====================================================================
-- 5. PROVISIONES: DÉCIMO TERCER MES Y VACACIONES
-- =====================================================================

CREATE TABLE provisiones_decimo (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contrato_id         UUID NOT NULL REFERENCES contratos(id),
    cuatrimestre        VARCHAR(20) NOT NULL,  -- 'dic-abr','abr-ago','ago-dic'
    anio                INTEGER NOT NULL,
    monto_acumulado     NUMERIC(12,2) NOT NULL DEFAULT 0,
    fecha_pago_programada DATE NOT NULL,       -- 15-abr, 15-ago, 15-dic
    pagado              BOOLEAN NOT NULL DEFAULT false,
    fecha_pago_real     DATE,
    movimiento_planilla_id UUID REFERENCES movimientos_planilla(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_provisiones_decimo_contrato ON provisiones_decimo(contrato_id);

CREATE TABLE provisiones_vacaciones (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contrato_id         UUID NOT NULL REFERENCES contratos(id),
    fecha_inicio_periodo DATE NOT NULL,        -- inicio del período de 11 meses
    dias_acumulados     NUMERIC(6,2) NOT NULL DEFAULT 0,
    dias_gozados        NUMERIC(6,2) NOT NULL DEFAULT 0,
    monto_provisionado  NUMERIC(12,2) NOT NULL DEFAULT 0,
    estado              VARCHAR(20) NOT NULL DEFAULT 'abierto', -- 'abierto','liquidado'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_provisiones_vacaciones_contrato ON provisiones_vacaciones(contrato_id);

-- =====================================================================
-- 6. LIQUIDACIONES (terminación de la relación laboral)
-- =====================================================================

CREATE TABLE liquidaciones (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contrato_id             UUID NOT NULL REFERENCES contratos(id),
    fecha_terminacion       DATE NOT NULL,
    motivo                  VARCHAR(50) NOT NULL,
    decimo_proporcional     NUMERIC(12,2) NOT NULL DEFAULT 0,
    vacaciones_pendientes   NUMERIC(12,2) NOT NULL DEFAULT 0,
    preaviso                NUMERIC(12,2) NOT NULL DEFAULT 0,
    indemnizacion           NUMERIC(12,2) NOT NULL DEFAULT 0,
    otras_deducciones       NUMERIC(12,2) NOT NULL DEFAULT 0,
    monto_total             NUMERIC(12,2) NOT NULL DEFAULT 0,
    estado                  VARCHAR(20) NOT NULL DEFAULT 'borrador', -- 'borrador','aprobada','pagada'
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_liquidaciones_contrato ON liquidaciones(contrato_id);

-- =====================================================================
-- 7. AUDITORÍA BÁSICA (recomendado para nómina por temas legales)
-- =====================================================================

CREATE TABLE auditoria_cambios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tabla_afectada  VARCHAR(100) NOT NULL,
    registro_id     UUID NOT NULL,
    usuario_id      UUID REFERENCES usuarios(id),
    accion          VARCHAR(20) NOT NULL,  -- 'insert','update','delete'
    datos_anteriores JSONB,
    datos_nuevos    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_auditoria_tabla_registro ON auditoria_cambios(tabla_afectada, registro_id);

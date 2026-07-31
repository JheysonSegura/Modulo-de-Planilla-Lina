-- =====================================================================
-- MIGRACIÓN: SOPORTE MULTI-EMPRESA (MULTI-TENANT)
-- Permite que un mismo usuario (ej. un contador) administre múltiples
-- empresas desde una sola instalación de la app.
-- =====================================================================

-- =====================================================================
-- 1. TABLA DE EMPRESAS (nuevo nivel raíz del modelo)
-- =====================================================================

CREATE TABLE empresas (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    razon_social        VARCHAR(200) NOT NULL,
    nombre_comercial    VARCHAR(200),
    ruc                 VARCHAR(30) NOT NULL,
    dv                  VARCHAR(5),                  -- dígito verificador del RUC
    numero_patronal_css VARCHAR(30),                 -- número de empleador asignado por la CSS
    clase_riesgo        VARCHAR(20),                 -- I, II, III, IV, V - referencia a tasas_riesgo_profesional
    direccion           TEXT,
    telefono            VARCHAR(30),
    email_contacto      VARCHAR(150),
    representante_legal VARCHAR(200),
    moneda              VARCHAR(10) NOT NULL DEFAULT 'USD',
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ruc)
);

-- =====================================================================
-- 2. RELACIÓN USUARIOS <-> EMPRESAS (muchos a muchos, con rol por empresa)
-- Esto es lo que permite que el contador tenga acceso a sus 14 empresas
-- con un solo login, y que cada empresa cliente tenga su propio admin.
-- =====================================================================

CREATE TABLE usuarios_empresas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    empresa_id      UUID NOT NULL REFERENCES empresas(id),
    rol_id          INTEGER NOT NULL REFERENCES roles(id),
    activo          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (usuario_id, empresa_id)
);

CREATE INDEX idx_usuarios_empresas_usuario ON usuarios_empresas(usuario_id);
CREATE INDEX idx_usuarios_empresas_empresa ON usuarios_empresas(empresa_id);

-- Nota de diseño: quité rol_id de la tabla `usuarios` (si ya lo tenías ahí
-- de la versión anterior) porque el rol ahora es POR EMPRESA, no global.
-- El mismo contador puede ser 'admin' en su propia empresa y 'contador'
-- (procesa planilla, no borra nada) en las empresas de sus clientes.
ALTER TABLE usuarios DROP COLUMN IF EXISTS rol_id;

-- =====================================================================
-- 3. AGREGAR empresa_id A LAS TABLAS OPERATIVAS EXISTENTES
-- =====================================================================

ALTER TABLE empleados ADD COLUMN empresa_id UUID REFERENCES empresas(id);
CREATE INDEX idx_empleados_empresa ON empleados(empresa_id);

-- La identificación (cédula/pasaporte) ya no puede ser única globalmente,
-- porque la misma persona puede trabajar legítimamente en dos empresas
-- distintas administradas por el mismo contador.
ALTER TABLE empleados DROP CONSTRAINT IF EXISTS empleados_tipo_identificacion_identificacion_key;
ALTER TABLE empleados ADD CONSTRAINT uq_empleados_empresa_identificacion
    UNIQUE (empresa_id, tipo_identificacion, identificacion);

ALTER TABLE contratos ADD COLUMN empresa_id UUID REFERENCES empresas(id);
CREATE INDEX idx_contratos_empresa ON contratos(empresa_id);

ALTER TABLE planillas ADD COLUMN empresa_id UUID REFERENCES empresas(id);
CREATE INDEX idx_planillas_empresa ON planillas(empresa_id);

ALTER TABLE liquidaciones ADD COLUMN empresa_id UUID REFERENCES empresas(id);
CREATE INDEX idx_liquidaciones_empresa ON liquidaciones(empresa_id);

ALTER TABLE provisiones_decimo ADD COLUMN empresa_id UUID REFERENCES empresas(id);
ALTER TABLE provisiones_vacaciones ADD COLUMN empresa_id UUID REFERENCES empresas(id);

-- movimientos_planilla y conceptos_variables heredan el aislamiento a
-- través de planillas/movimientos_planilla respectivamente, así que no
-- necesitan empresa_id propio -- pero si tu volumen crece mucho y
-- quieres activar Row-Level Security directo sobre ellas, se puede
-- denormalizar empresa_id ahí también más adelante sin romper nada.

-- =====================================================================
-- 4. ROW-LEVEL SECURITY (aislamiento a nivel de base de datos)
-- Esto es una capa EXTRA de seguridad además de tu lógica en FastAPI:
-- aunque un bug en el backend arme mal un query, Postgres no devuelve
-- filas de una empresa a la que el usuario no tiene acceso.
-- =====================================================================

ALTER TABLE empleados ENABLE ROW LEVEL SECURITY;
ALTER TABLE contratos ENABLE ROW LEVEL SECURITY;
ALTER TABLE planillas ENABLE ROW LEVEL SECURITY;

-- Ejemplo de política: se asume que la app setea, al iniciar cada
-- conexión/transacción, la variable de sesión 'app.empresa_actual'
-- con el empresa_id activo (esto lo haces en FastAPI vía dependency
-- que corre `SET LOCAL app.empresa_actual = '<uuid>'` al abrir la
-- transacción, después de validar en usuarios_empresas que el usuario
-- tiene acceso a esa empresa).

CREATE POLICY empresa_aislamiento_empleados ON empleados
    USING (empresa_id = current_setting('app.empresa_actual')::uuid);

CREATE POLICY empresa_aislamiento_contratos ON contratos
    USING (empresa_id = current_setting('app.empresa_actual')::uuid);

CREATE POLICY empresa_aislamiento_planillas ON planillas
    USING (empresa_id = current_setting('app.empresa_actual')::uuid);

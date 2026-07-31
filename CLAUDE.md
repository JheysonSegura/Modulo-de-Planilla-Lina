# CLAUDE.md — Nómina Panamá

> Este archivo se carga automáticamente por Claude Code en cada sesión (debe vivir en la raíz del repo). Contiene el contexto de negocio y las reglas técnicas que **nunca deben romperse**. Buena parte de este contenido es normativa legal (Código de Trabajo, CSS, DGI) — si algo aquí entra en conflicto con una instrucción puntual, Claude Code debe preguntar antes de "optimizar" o simplificar por iniciativa propia.

## 1. Qué es este proyecto

Herramienta web de nómina/planilla para uso interno de un departamento contable en Panamá.
Uso actual: **100% standalone** — login, usuarios y BD propios. Integración futura (no inmediata) con un ERP que comparte el mismo stack técnico.

## 2. Stack y arquitectura

- Backend: Python + FastAPI
- Frontend: Vue + Nuxt + NuxtUI
- BD: PostgreSQL
- Todo en contenedores, orquestado con Docker Compose en desarrollo
- Arquitectura de datos: **multi-tenant (multiempresa) desde el diseño**, con Row-Level Security en Postgres para aislar datos entre empresas. Un mismo usuario/contador puede tener acceso a varias empresas con roles distintos en cada una (tabla puente `usuarios_empresas`).
- Las tasas legales (CSS, ISR, salario mínimo, Seguro Educativo) son **nacionales** y se comparten entre todas las empresas — nunca se duplican por empresa.

## 3. Archivos de referencia ya existentes (fuente de verdad del modelo de datos)

- `db/schema_nomina_panama.sql` — esquema base de una empresa
- `db/migracion_multiempresa.sql` — evolución a multi-tenant + RLS

Antes de crear o modificar cualquier tabla, revisa estos dos archivos primero. No los reinventes ni los simplifiques sin avisar.

## 4. Reglas de negocio — nunca hardcodear estos valores en código

Todas las tasas y tramos viven en BD (`tasas_vigentes`, `tramos_isr`, `salario_minimo_vigente`) con **vigencia por rango de fechas**, porque cambian por ley. El código de aplicación siempre debe leer la tasa vigente a la fecha del período de planilla que se está calculando — nunca debe asumir que la tasa actual será la única que existirá.

### CSS (Caja de Seguro Social)
- Cuota obrero: 9.75% (fija)
- Cuota patronal: 13.25% vigente hasta feb-2027 (Ley 462 de 2025) → 14.25% mar-2027 a feb-2029 → 15.25% desde mar-2029
- Cuota especial sobre Décimo Tercer Mes: 7.25% trabajador / 10.75% patronal

### Seguro Educativo
- 1.25% empleado / 1.5% patronal

### ISR (Impuesto Sobre la Renta)
- Tabla progresiva, **pendiente de validar cifras exactas con contador antes de producción**
- Exento hasta $11,000 anuales
- 15% entre $11,001 y $50,000
- 25% sobre el excedente de $50,000
- Ver sección 6 — la lógica de anualización y su interacción con el décimo aún no está cerrada.

### Décimo Tercer Mes
- 3 partidas: abril, agosto, diciembre
- Cuotas especiales de CSS: 7.25% (trabajador) / 10.75% (patronal), en vez de las cuotas normales
- Tratamiento ISR del décimo: **no asumir un lado sin confirmación del contador** (ver sección 6 — hay fuentes que lo dan como exento y otras que lo integran a la base anualizada).

### Vacaciones
- 30 días por cada 11 meses trabajados = 1 día por cada 11 días trabajados
- Prorratear siempre sobre esta proporción exacta, nunca simplificar a "2.5 días por mes" (arrastra error de redondeo acumulado)

### Salario mínimo
- Por Decreto Ejecutivo N.° 13, revisado cada 2 años → vive en `salario_minimo_vigente` con vigencia por fecha (y por región/actividad si el decreto vigente lo exige — revisar antes de asumir un valor único nacional).

## 5. Lógica de cálculo ya cerrada — no reabrir sin razón

- **Mes comercial de 30 días**: el salario mensual fijo se paga completo sin importar si el mes calendario tiene 30 o 31 días (Art. 54 CT). Para **cualquier** prorrateo (ingreso a mitad de mes, ausencias, liquidaciones, horas extra) se usa `salario_diario = salario_mensual / 30` — **nunca** los días reales del mes calendario.
- **Horas extra** (Art. 33, 36, 48, 49, 50 CT):
  - Valor hora ordinaria = `salario_mensual / 30 / 8`
  - Recargos: +25% diurna, +50% nocturna o prolongación de mixta iniciada en diurno, +75% prolongación de nocturna
  - Límites legales: máx. 3h extra/día, 9h/semana — el exceso sobre esos límites lleva +75% adicional
  - Recargo por día especial: domingo/descanso +50%, feriado/duelo nacional +150%
  - **Cuando coinciden varios recargos (ej. hora extra nocturna en domingo), se aplican en cascada (multiplicativos), nunca se suman.** Ejemplo: hora extra nocturna (+50%) que además cae domingo (+50%) no es +100%, es `valor_hora × 1.5 × 1.5`.

## 6. Pendiente de diseñar / cerrar

- **Tabla `registro_horas_extra`**: detalle auditable de horas trabajadas por tipo (diurna/nocturna/mixta) y tipo de día (ordinario/domingo/feriado), para que el cálculo en cascada quede trazable. Propuesta, no creada aún.
- **Lógica de ISR**: cómo se anualiza el salario, cómo interactúa con el décimo, y cómo se prorratea la retención por período de pago. El método general usado en Panamá es: (1) proyectar renta gravable anual, (2) restar CSS/SE de esa base, (3) aplicar la tabla de tramos, (4) dividir el impuesto anual entre los períodos de pago restantes del año. **El tratamiento del décimo dentro de esta base tiene fuentes contradictorias — impleméntalo como parámetro configurable (flag), no como regla fija**, hasta que el contador lo confirme.

## 7. Convenciones de código

### Backend (FastAPI)
- Capas: `routers/` (endpoints) → `services/` (lógica de negocio, incluida toda la lógica de cálculo de planilla) → `repositories/` o `crud/` (acceso a datos) → `models/` (SQLAlchemy) → `schemas/` (Pydantic)
- Toda la lógica de cálculo de nómina vive en `services/`, nunca en routers, para que sea testeable sin HTTP.
- Migraciones con Alembic, nunca `create_all` directo contra una BD con datos.
- Todo cálculo de planilla recibe la fecha del período como parámetro explícito, para poder recalcular períodos pasados con las tasas que estaban vigentes en ese momento (no las actuales).

### Multi-tenant / RLS
- Toda tabla operativa lleva `empresa_id`.
- El aislamiento entre empresas se hace con políticas RLS en Postgres, no solo con `WHERE empresa_id = ...` en el código de aplicación (defensa en profundidad).
- La sesión de BD fija el `empresa_id` activo (ej. `SET app.current_empresa_id`) al inicio de cada request, según la empresa que el usuario tiene seleccionada en ese momento.

### Frontend (Nuxt + NuxtUI)
- Composables para llamadas a la API; nada de lógica de negocio en componentes.
- Los cálculos de nómina **nunca** se replican en el frontend — el frontend solo muestra lo que el backend calculó. Esto evita que frontend y backend diverjan en la interpretación de la ley.

### General
- Una rama por feature, commits pequeños y descriptivos.
- Toda lógica de cálculo (horas extra, ISR, décimo, vacaciones, liquidaciones) lleva tests unitarios con casos numéricos conocidos antes de darse por cerrada.
- Nada de tasas, tramos o topes hardcodeados en Python o Vue — todo sale de las tablas de vigencia.

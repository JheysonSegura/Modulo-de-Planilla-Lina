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
- Tabla progresiva, **CONFIRMADA con fuente oficial** — método confirmado por el contador el 2026-08-04 con caso numérico, y cifras de tramos confirmadas el 2026-08-05 contra la tarifa oficial de la DGI (https://dgi.mef.gob.pa/DInforme/Tarifa).
- Exento hasta $11,000 anuales
- 15% entre $11,001 y $50,000
- Sobre $50,000: $5,850.00 (= 15% de los primeros $50,000 gravables, es decir 15% × $39,000 de excedente sobre el tramo exento) + 25% sobre el excedente de $50,000

### Décimo Tercer Mes
- 3 partidas: 15 de abril, 15 de agosto, 15 de diciembre — **fecha confirmada por el contador el 2026-08-05** (el decreto original de 1971 decía 15 de marzo/agosto/diciembre; la práctica actual movió la primera partida a abril).
- Cuotas especiales de CSS: 7.25% (trabajador) / 10.75% (patronal), en vez de las cuotas normales — **confirmado por el contador el 2026-08-05** como práctica vigente (el decreto original de 1971 declaraba el décimo exento de CSS; esa exención ya no aplica).
- **Tratamiento ISR del décimo: CONFIRMADO por el contador (2026-08-04 y 2026-08-05) — se integra a la base anualizada** como un mes adicional de salario (12 meses regulares + 1 de décimo = 13). Umbral mensual equivalente: salario bruto mensual < B/.846.15 (= $11,000/13) no genera ISR ni en salario regular ni en el décimo. Ver sección 6.

### Vacaciones
- 30 días por cada 11 meses trabajados = 1 día por cada 11 días trabajados
- Prorratear siempre sobre esta proporción exacta, nunca simplificar a "2.5 días por mes" (arrastra error de redondeo acumulado)

### Salario mínimo
- Por Decreto Ejecutivo N.° 13, revisado cada 2 años → vive en `salario_minimo_vigente` con vigencia por fecha, región, actividad económica y tamaño de empresa.
- **Desglose real cargado** (Decreto Ejecutivo N.13 de 31-dic-2025, Gaceta Oficial N.30438, vigente desde 2026-01-16): 146 filas, ~98 actividades × Región 1/Región 2/Nacional, casi todo tarifa **por hora** (no mensual) — excepto Trabajador Doméstico, la única fila mensual ($350 Región 1 / $320 Región 2). Equivalente mensual de una tarifa por hora: `monto_hora × 8 × 30` (mismo mes comercial de 30 días y jornada de 8h del resto del proyecto).
- `tamano_empresa` (`'Pequeña Empresa'` / `'Gran Empresa'`) es una declaración **manual** del admin en `empresas.tamano_empresa` — el sistema no cuenta empleados para inferirlo. El umbral real de empleados que distingue pequeña/gran varía por sector (11/14-15/16 según la actividad); esa cifra vive solo en el decreto, no en una columna.
- **Limitación conocida:** varias filas del decreto se dividen por OCUPACIÓN específica dentro de una empresa (ej. conductores de buses, talladores de casino, abogados, técnicos de salud), no por tamaño. La resolución automática (`salario_minimo_service._elegir_fila_aplicable`) es a nivel EMPRESA (`empresas.actividad_economica`), no por empleado/contrato — una empresa con roles mixtos no puede seleccionar automáticamente la fila de ocupación correcta por ahora. Revisar si algún cliente real lo necesita antes de construir un override por contrato.
- La fila placeholder de $605/mes (referencia general, ya no vigente) sigue en BD con `fecha_fin = 2026-01-15` para poder calcular retroactivamente el 1-15 de enero de 2026.

## 5. Lógica de cálculo ya cerrada — no reabrir sin razón

- **Mes comercial de 30 días**: el salario mensual fijo se paga completo sin importar si el mes calendario tiene 30 o 31 días (Art. 54 CT). Para **cualquier** prorrateo (ingreso a mitad de mes, ausencias, liquidaciones, horas extra) se usa `salario_diario = salario_mensual / 30` — **nunca** los días reales del mes calendario.
- **Horas extra** (Art. 33, 36, 48, 49, 50 CT):
  - Valor hora ordinaria = `salario_mensual / 30 / 8`
  - Recargos: +25% diurna, +50% nocturna o prolongación de mixta iniciada en diurno, +75% prolongación de nocturna
  - Límites legales: máx. 3h extra/día, 9h/semana — el exceso sobre esos límites lleva +75% adicional
  - Recargo por día especial: domingo/descanso +50%, feriado/duelo nacional +150%
  - **Cuando coinciden varios recargos (ej. hora extra nocturna en domingo), se aplican en cascada (multiplicativos), nunca se suman.** Ejemplo: hora extra nocturna (+50%) que además cae domingo (+50%) no es +100%, es `valor_hora × 1.5 × 1.5`.
- **Registro de horas extra**: implementado en `registro_horas_extra` (Fase 5) — detalle auditable por tipo de hora/día, con el cálculo en cascada trazable en `app/services/horas_extra_service.py`.
- **ISR (método confirmado por el contador el 2026-08-04 con caso numérico verificado; cifras de tramos confirmadas el 2026-08-05 contra la tarifa oficial de la DGI — ver `app/services/planilla_service.py::_calcular_isr_retenido` y `FASE7-plan-isr.txt`)**:
  1. Renta bruta anual proyectada = `salario_mensual_vigente × 13` (12 meses regulares + 1 de décimo — el décimo **sí** se integra a la base, no es exento).
  2. **No se resta CSS/SE de esa base.** El excedente gravable se calcula directo sobre la renta bruta anual (con décimo incluido).
  3. Se resta el tramo exento ($11,000) y se aplica la tasa marginal del tramo correspondiente sobre el excedente, sumando la base acumulada de tramos previos (ver `tramos_isr`: tramo 3 tiene `impuesto_base=5850`, que es 15% × $39,000, el excedente gravable del tramo 2).
  4. El impuesto anual resultante se prorratea entre los períodos de pago **restantes** del año, reconciliando contra lo ya retenido en períodos previos del mismo año calendario (ajuste progresivo) para que un cambio de salario a mitad de año no sub ni sobre-retenga.
  - Caso de verificación del contador: salario $2,500/mes → bruto anual con décimo $32,500 → excedente sobre $11,000 = $21,500 → 15% = $3,225.00 anual → $268.75/mes.
  - Tramos verificados contra `tramos_isr` sembrado en `0003_seed_tasas_legales.py`: coincide exacto con la tarifa oficial DGI (0/11000/0.00, 11000/50000/0.15, 50000/NULL/0.25 con base 5850). No requiere cambios de código ni de datos.

## 6. Pendiente de diseñar / cerrar

- Nada pendiente de diseño en ISR/horas extra/décimo a la fecha (2026-08-05) — ver sección 5. ISR cerrado en método y cifras de tramos (contador + DGI). Décimo cerrado en fórmula, fechas de pago y CSS especial (contador).
- Sigue pendiente: la tasa de riesgo profesional patronal (CSS), y el override por contrato para filas de salario mínimo divididas por ocupación específica (ver sección 4).

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

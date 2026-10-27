# Plan — Descuentos de ley en el pago de vacaciones

## Contexto

Hoy `vacaciones_service.registrar_vacacion_tomada` solo calcula el bruto (`días × salario/30`) y el recibo de vacaciones lo muestra tal cual: **sin CSS, Seguro Educativo ni ISR, y sin aportes patronales**. Además, el pago de vacaciones y las quincenas regulares no se conocen entre sí: si alguien se va de vacaciones del 1 al 30 de marzo, las quincenas de marzo igual le pagan el salario completo (doble pago).

Decisiones confirmadas por el usuario (2026-10-23):
1. El pago de vacaciones **reemplaza** el salario de esos días en las quincenas regulares.
2. ISR = **lo mismo que el mes que reemplaza**: `(impuesto anual proyectado ÷ 12) × (días ÷ 30)`.
3. Se procesa como una **planilla propia de vacaciones** (igual que el décimo): borrador → aprobar → pagar con constancia, con recibo y aportes patronales. Se alinea con el Art. 54.5 CT (pago 3 días antes del descanso).

Nota legal: los artículos 54–56 del CT (verificados contra `código-detrabajo.pdf`) fijan el monto y el momento del pago. Los descuentos vienen de la Ley Orgánica de la CSS y de la DGI: el pago de vacaciones es salario y lleva las mismas cuotas que una quincena normal.

## Diseño

### 1. Modelo de datos — migración `0039_vacaciones_planilla`
- `vacaciones_tomadas`: agregar `fecha_fin_goce` (date, = `fecha + días − 1`, días calendario), `movimiento_planilla_id` (FK nullable a `movimientos_planilla`) y `anulada` (bool, default false). `fecha` pasa a significar formalmente "fecha de inicio del descanso". Las filas viejas quedan con `movimiento_planilla_id = NULL` (sin descuentos, recibo como antes).
- Nuevo valor de `planillas.tipo`: `'vacaciones'` (VARCHAR(20) libre, no hay CHECK, no hace falta alterar la columna).
- Ojo: revisión de alembic de 32 caracteres o menos, y correr la migración también contra la BD de dev.

### 2. Backend — `app/services/vacaciones_service.py`
`registrar_vacacion_tomada` (misma firma más `fecha_pago` opcional; por defecto `fecha − 3 días`, Art. 54.5):
- **Nueva validación (422)**: rechaza si el rango del descanso se solapa con una planilla regular no anulada que ya incluye a este contrato. Pide anular primero ese borrador; si no, habría doble pago.
- Mantiene la lógica FIFO actual de días y provisiones sin cambios.
- Crea `Planilla(tipo='vacaciones', periodo_inicio=fecha, periodo_fin=fecha_fin_goce, fecha_pago, estado='borrador')` más un `MovimientoPlanilla` con:
  - `salario_bruto` = suma de los montos de los eventos (igual que hoy).
  - CSS 9.75% / 13.25%, SE 1.25% / 1.5% y riesgo profesional patronal → mismas tasas que una quincena (`tasas_vigentes` a la `fecha_pago`, mismo criterio que `decimo_service.generar_pago_decimo`).
  - ISR → nueva función compartida en `planilla_service` (ver 3) × `días/30`.
  - Llena `isr_renta_anual_proyectada`/`isr_impuesto_anual_proyectado` para auditoría.
- Enlaza cada `VacacionTomada` del evento con `movimiento_planilla_id`.
- Nueva función `revertir_toma_de_planilla(db, planilla)`: devuelve los días a cada provisión (al período `abierto` se le resta de `dias_gozados`; al `acumulado` se le resta y además se le repone `monto_provisionado += días × valor_dia`) y marca los eventos `anulada=True`.

### 3. Backend — `app/services/planilla_service.py`
- Extraer de `_calcular_isr_retenido` el cálculo del **impuesto anual proyectado** (salario×12 + décimo, tramo) a `calcular_impuesto_anual_proyectado(db, salario_mensual, fecha)` y reusarlo desde vacaciones. No se duplica la lógica de tramos.
- `_calcular_movimiento_de_contrato`: nuevo descuento por días de vacaciones dentro del período = **días calendario del descanso que caen en el período, sin pasar de los días comerciales del período (15/30)**. Se descuenta de `salario_base_periodo` (mínimo 0) y se agrega un `ConceptoVariable` `informativo` `vacaciones_pagadas_aparte`, igual que la ausencia sin goce.
- ISR de la quincena × `(días comerciales del período − días de vacaciones) / días comerciales del período`. La reconciliación anual existente (`sumar_isr_retenido_del_anio`, que ya suma todas las planillas no anuladas, incluida la de vacaciones) ajusta cualquier diferencia en las quincenas siguientes.
- `anular_planilla`: si `tipo == 'vacaciones'` → llama `vacaciones_service.revertir_toma_de_planilla`.
- Sin cambios: décimo (ya cuenta los días de vacaciones como devengados vía `historial_salarial`), provisión de vacaciones, promedios de liquidación (regular reducido + planilla de vacaciones = mismo total) y `obtener_ultimo_periodo_fin_pagado` (ya filtra mensual/quincenal).

### 4. Reportes
- `reportes_service.armar_recibo_vacacion`: si el evento tiene movimiento, agrega bruto, CSS, SE, ISR y **neto a pagar**, y una sección patronal opcional. `recibo_vacacion.html` muestra esa sección. Eventos viejos sin movimiento: igual que hoy.
- `recibo_pago.html`: título "Recibo de pago — Vacaciones" cuando `planilla_tipo == 'vacaciones'`. La exportación de la planilla y el ZIP de recibos funcionan genéricos.

### 5. Frontend
- `VacacionesTab.vue`: etiqueta "Fecha de inicio del descanso", campo opcional "Fecha de pago" (se sugiere inicio − 3 días), y en la lista de eventos: bruto/neto, estado de su planilla, link a la planilla y marca de "anulada".
- `useVacaciones.ts`: tipos nuevos (`fecha_pago`, `fecha_fin_goce`, `planilla_id`, `salario_neto`, `anulada`).
- `planillas/index.vue`: filtro "Vacaciones". El detalle `[id].vue` ya es genérico.

### 6. Documentación
- CLAUDE.md sección 4 "Vacaciones": la regla nueva, la fórmula de ISR y la decisión de planilla propia. Archivo `FASE-vacaciones-descuentos.txt` al cerrar, con las cifras verificadas.

## Casos numéricos para validar con el contador (se dejan como tests)

**A. $2,500/mes, 30 días del 1 al 30 de mar 2026**
- Bruto $2,500.00
- CSS $243.75, SE $31.25, ISR $268.75 (= $3,225/12)
- **Neto $1,956.25**
- Patronal: CSS $331.25, SE $37.50
- Quincenas de marzo: salario $0, ISR $0
- 1ª quincena de abril: ISR $134.38 (normal, la reconciliación cuadra)

**B. $900/mes, 15 días del 1 al 15 de mar**
- Bruto $450.00, CSS $43.88, SE $5.62, ISR $4.38, **neto $396.12**
- Es idéntico a la quincena base de Bruno ya confirmada en la Fase 17. Sirve de prueba de coherencia: 15 días de vacación = una quincena normal.

**Puntos a confirmar con el contador (no bloquean, quedan documentados):**
1. Vacación de 30 días en mes de 31 días que no arranca el día 1 (ej. del 2 al 31 de mar): con la regla de "días calendario sin pasar de 15", la quincena del 1 al 15 paga 1 día y el mes totaliza 31 días pagados.
2. La tasa de CSS se toma a la fecha de pago (igual que el décimo).
3. Laguna preexistente, no se toca: el Art. 54.2 pide pagar el promedio de 11 meses si es más favorable (comisiones, horas extra). Hoy solo se usa el salario vigente ÷ 30.

## Archivos críticos
- `backend/app/services/vacaciones_service.py`, `planilla_service.py`, `reportes_service.py`
- `backend/app/models/provisiones.py`, `backend/app/repositories/provisiones_vacaciones.py`, `movimientos_planilla.py` (consulta de solape), `backend/app/schemas/vacaciones.py`, `backend/app/routers/vacaciones.py`
- `backend/alembic/versions/0039_*.py`, `backend/app/templates/recibo_vacacion.html`, `recibo_pago.html`
- `frontend/app/components/contrato/VacacionesTab.vue`, `composables/useVacaciones.ts`, `pages/planillas/index.vue`

## Verificación
1. Tests nuevos en `backend/tests/test_vacaciones.py`: casos A y B exactos, quincena con salario/ISR en cero, solape parcial (del 10 de mar al 8 de abr), rechazo por solape con una planilla regular ya generada, anular planilla de vacaciones → saldo restaurado y eventos anulados, recibo con descuentos (`test_reportes_service.py`).
2. Suite completa (`docker compose exec backend pytest -q`), incluida `tests/regresion` sin cambios en sus cifras. Revisar que ningún test viejo cambie de resultado.
3. `alembic upgrade head` contra la BD de dev; `npm run lint` y `npm run typecheck`; `docker compose restart frontend`.
4. Navegador real (Empresa Demo): registrar vacación → ver la planilla de vacaciones en borrador → aprobar/pagar → descargar el recibo con neto → generar las quincenas de marzo y verificar salario 0 → anular un caso de prueba y verificar que el saldo vuelve. Limpiar los datos de prueba al cerrar.
5. Al cerrar: desglose de qué se probó en vivo y qué se infirió, y preguntar por el commit.

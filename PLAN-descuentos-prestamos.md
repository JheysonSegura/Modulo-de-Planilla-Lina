# PLAN — Descuentos recurrentes (préstamos, bancos, hipoteca, cooperativa, pensión, embargo)

Estado: **IMPLEMENTADO** (2026-11-17), con los ajustes de las secciones 4 y 5. 252 tests en verde (12 nuevos en `backend/tests/test_descuentos.py`), lint y typecheck limpios, verificado en navegador.

## 1. Base legal (verificada contra `código-detrabajo.pdf`)

| Tipo (código) | Artículo | Tope individual | Entra en tope total 50% |
|---|---|---|---|
| `prestamo_empresa` — anticipos / préstamos de la empresa | 161.3 | 15% del salario devengado en el período | Sí |
| `prestamo_bancario` — bancos, financieras, créditos comerciales | 161.11 | 20% | Sí |
| `hipoteca` — cuota de vivienda (entidad vendedora o crediticia) | 161.4 | 30% | Sí |
| `cooperativa` — cooperativas, ahorro, bancos obreros | 161.5 | sin tope propio | Sí |
| `pension_alimenticia` — ordenada por autoridad competente | 161.6 | sin tope propio | **No** (161.13) |
| `embargo` — orden judicial | 161.7 / 162 | 15% del **excedente sobre el salario mínimo** (lo que no pase del mínimo es inembargable) | Sí |

- Art. 165: los préstamos de la empresa **no generan intereses** (salvo vivienda) → el préstamo de la empresa se registra solo por su monto principal; no habrá campo de interés.
- Art. 161.11: la autorización de descuento a bancos es irrevocable → el usuario no puede "pausar" un descuento bancario por su cuenta, solo cerrarlo con un motivo (ej. carta de cancelación del banco).
- Art. 164: al terminar la relación se pueden hacer los descuentos del 161 sobre el último salario por obligaciones exigibles → base del descuento del préstamo de la empresa en la liquidación.
- **Topes en BD, no en código** (regla del CLAUDE.md): se siembran en `tasas_vigentes` con vigencia (`tope_desc_prestamo_empresa` 0.15, `tope_desc_prestamo_bancario` 0.20, `tope_desc_hipoteca` 0.30, `tope_desc_embargo_excedente` 0.15, `tope_desc_total` 0.50).

## 2. Decisiones del usuario (2026-11-17)

1. Se cubren **los 6 tipos** de la tabla.
2. Si una cuota pasa un tope: **solo avisar** — se descuenta la cuota completa y se muestra una advertencia en la planilla.
3. Las cuotas se cobran en la planilla regular **y en el pago de vacaciones** (corregido por el usuario 2026-11-17, ver sección 4); nunca en el décimo.
4. Liquidación:
   - Deudas con bancos/financieras/cualquier tercero: **no se descuentan** — cada persona sigue pagando por su cuenta. Al liquidar, esos descuentos se cierran automáticamente (motivo "terminación del contrato").
   - Préstamo de la empresa: se descuenta el saldo, con **una casilla marcada por defecto**. Si el usuario la desmarca, aparece un campo de **monto manual** y otro de **observación** (obligatoria).

## 3. Diseño propuesto

### Datos (migración `0040_descuentos_recurrentes`, con `empresa_id` + RLS desde el día uno)

`descuentos_recurrentes`: contrato, tipo, acreedor (nombre de la entidad), referencia (n.º de carta/préstamo/expediente), monto_total y plazo_meses (vacíos en pensión y cooperativa = sin fin), frecuencia (`mensual`/`quincenal`), numero_cuotas y cuota (calculadas al registrar), fecha_inicio (primer cobro), estado (`activo` / `pagado` / `cerrado`), motivo de cierre, documento adjunto opcional (carta del banco u orden judicial, igual que en ausencias), observación.

Cada cuota cobrada queda como un `ConceptoVariable` tipo `deduccion` del movimiento de planilla, con enlace al descuento (`descuento_recurrente_id`). El **saldo se calcula** (monto_total − cuotas en planillas no anuladas), no se guarda: así, anular una planilla en borrador devuelve la cuota al saldo sin código extra.

### Motor de planilla (`planilla_service._calcular_movimiento_de_contrato`)

- Por cada descuento `activo` del contrato con `fecha_inicio <= periodo_fin`: cobra la cuota (la última cuota se limita al saldo restante; al llegar a saldo 0 pasa a `pagado` cuando se aprueba la planilla).
- Suma a `otras_deducciones` (igual que los descuentos puntuales actuales: baja el neto, no la base de CSS/SE/ISR).
- Calcula advertencias contra los topes de la sección 1 usando el `salario_bruto` del período, y las muestra en el detalle de la planilla (no cambian ningún total).

### Liquidación (`liquidaciones_service`)

- Nuevo concepto "Préstamo de la empresa" que **resta** del total (como la penalidad del Art. 222). Request: `descontar_prestamo_empresa: bool = True`; si es `False` → `monto_prestamo_manual` + `observacion_prestamo` obligatoria.
- **Compatibilidad**: si el contrato no tiene préstamo de la empresa activo, el resultado de cualquier llamada existente no cambia (lección de la Fase 13).
- Anular la liquidación revierte el descuento y reabre los descuentos que cerró.

### Frontend

- Nueva pestaña **"Descuentos"** en el contrato: lista con tipo, acreedor, cuota, saldo, estado y el historial de cuotas cobradas; formulario de alta; botón cerrar (con motivo).
- Detalle de planilla y recibo PDF/Excel: cada cuota aparece con su acreedor (ej. "Préstamo Banco General — ref. 12345"), y las advertencias de tope en el detalle.
- Liquidación: casilla + monto manual + observación.

### Permisos y auditoría

Crear/cerrar descuentos: admin y contador (igual que el resto de la operación); consulta solo lectura. Alta, cierre y la decisión de la liquidación quedan en `auditoria_cambios`.

## 4. Decisiones finales del usuario (2026-11-17)

1. **Registro**: monto, plazo en meses y frecuencia (`mensual`/`quincenal`), tal como el usuario lo registre. Quincenal = 2 cuotas por mes; mensual = 1 cuota por mes. Cuota = monto ÷ n.º de cuotas, la última absorbe los centavos.
   - Fechas de cobro: quincenal → el 15 y el último día de cada mes; mensual → el último día de cada mes (en una empresa con planilla quincenal cae en la 2.ª quincena). Una planilla cobra las cuotas cuya fecha de cobro cae dentro de su período.
2. **Monto**: préstamo externo (banco, financiera, cualquier institución) = el monto que indica la carta; préstamo de la empresa = solo capital (Art. 165).
3. **Vacaciones**: el pago de vacaciones cobra las cuotas cuya fecha de cobro cae dentro del descanso (en base comercial, igual que el resto del sistema: un descanso que termina el día 30 de un mes de 31 cubre el cobro de fin de mes). Esas cuotas no se vuelven a cobrar en la quincena.
   - **El neto nunca queda negativo**: si lo disponible no alcanza, se cobra hasta dejar el neto en 0 y lo que falta queda en el saldo del préstamo (se cobra en las siguientes fechas de cobro), con advertencia.
4. **Reporte para pagar a los acreedores**: SÍ, en esta fase — Excel por planilla con lo descontado agrupado por acreedor y referencia.

## 5. Base de los topes — RESUELTO por el usuario 2026-11-17

- Todos estos descuentos se hacen del **salario neto** (después de CSS, Seguro Educativo e ISR), y los topes (15/20/30/50%) se miden contra ese neto del período. El 50% total suma solo estos descuentos (no los de ley); la pensión alimenticia queda fuera.
- Embargo: 15% del excedente del neto sobre el salario mínimo del período (salario mínimo que el sistema ya resuelve para la empresa).

## 6. Pruebas previstas

Tests con casos numéricos: cuota que termina el préstamo (última cuota parcial), planilla anulada que devuelve la cuota, advertencia de 15/20/30/50%, embargo sobre el excedente del mínimo, pensión fuera del 50%, liquidación con casilla marcada / monto manual / sin préstamo (resultado idéntico al actual), cierre automático de los bancarios al liquidar. Luego, validación manual en navegador con Docker.

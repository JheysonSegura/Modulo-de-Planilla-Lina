# Suite de regresión — trimestre completo (Fase 17)

Suite de tests de integración que arma, contra la API real (vía `TestClient`,
mismo patrón que el resto de `backend/tests/`), un trimestre completo de
nómina quincenal para una empresa de prueba: salario fijo con ISR, salario
con horas extra, un pago de décimo, ausencias con justificación médica y sin
justificación, y una liquidación a mitad de período. Ver
`FASE17-plan-testing-integral.txt` en la raíz del repo para el diseño
completo y el estado de validación.

## Cómo correr

```bash
docker compose exec backend pytest tests/regresion -v
```

`-v` para ver cada test individual; agregar `-rs` para que el resumen final
liste el motivo exacto de cada skip (qué campo del fixture falta llenar):

```bash
docker compose exec backend pytest tests/regresion -v -rs
```

Correr solo esta suite es más rápido que la suite completa, pero antes de
cerrar cualquier cambio hay que correr `docker compose exec backend pytest -q`
completo (sin regresiones en el resto de los tests).

## Por qué la suite corre en verde sin números validados todavía

`fixtures_trimestre.py` define el escenario (empleados, fechas, eventos) y
un diccionario `ESPERADOS` con los montos que hay que verificar a mano con
el contador — **todos en `None` hasta que se llenen**. `test_trimestre_completo.py`
arma el escenario completo una sola vez (fixture `_escenario`, `scope="module"`)
y cada `test_*` compara una porción de `ESPERADOS` contra lo que devolvió la
API real:

- Si el bloque de `ESPERADOS` que le toca a ese test todavía tiene algún
  `None`, el test se **salta** (`pytest.skip`) con un mensaje que dice
  exactamente qué campo falta.
- Si ya está lleno, compara con `decimal.Decimal` exacto (mismo estilo que
  el resto de la suite) y falla si no coincide.

Como la construcción del escenario (crear los 5 contratos, registrar horas
extra y ausencias, generar las 6 planillas, liquidar a Elena, pagar el
décimo) corre siempre — no depende de `ESPERADOS` —, un `pytest` en verde
(con skips) ya confirma que el flujo completo no rompe con ningún error
HTTP. Los skips solo significan "todavía no hay un número humano contra el
cual comparar", nunca "no se probó nada".

## Cómo llenar el fixture

Abrir `fixtures_trimestre.py` y reemplazar cada `None` de `ESPERADOS` por un
**string** con el monto exacto (ej. `"832.50"`, nunca un float — el test
compara con `decimal.Decimal(str(valor))`, y un float puede perder
precisión antes de llegar a `Decimal`). Cada bloque de `ESPERADOS` tiene, en
un comentario justo arriba, el endpoint exacto que produce ese número:

| Bloque | Empleado / evento | De dónde sale el número |
|---|---|---|
| `ana_quincena_impar` / `ana_quincena_par` | Ana, $1,500/mes, sin novedades. `salario_bruto`/`css`/`seguro_educativo` son iguales en las 6 quincenas, pero `isr_retenido`/`salario_neto` alternan por paridad del período relativo del contrato (Q1/Q3/Q5 = impar, Q2/Q4/Q6 = par) -- ver CLAUDE.md sección 5, corrección 2026-08-18 | `GET /planillas/{id}/movimientos` |
| `bruno_quincena_base` | Bruno, $900/mes, quincenas Q1/Q3/Q5 (sin horas extra) | `GET /planillas/{id}/movimientos` |
| `bruno_horas_extra` | Bruno, quincenas Q2/Q4/Q6 (con horas extra) | `POST /contratos/{id}/horas-extra` (el registro) + `GET /planillas/{id}/movimientos` (el efecto en la quincena) |
| `quincena_base_800` | Carla y Diego, $800/mes (ninguna ausencia descuenta el salario, ver abajo) | `GET /planillas/{id}/movimientos` |
| `carla_provision_vacaciones_final` | Carla, tras las 6 quincenas | `GET /contratos/{id}/provisiones-vacaciones` (fila `estado="abierto"`) |
| `diego_provision_vacaciones_final` | Diego, tras las 6 quincenas | `GET /contratos/{id}/provisiones-vacaciones` (fila `estado="abierto"`) |
| `decimo.*` | Ana/Bruno/Carla/Diego, pago de décimo del cuatrimestre `dic-abr` 2026 | `POST /planillas/generar-decimo` + `GET /planillas/{id}/movimientos` |
| `liquidacion_elena` | Elena, `despido_injustificado` el 2026-02-20 | `POST /contratos/{id}/liquidacion` (respuesta directa) |

Una vez lleno un bloque, ese `pytest.skip` desaparece solo y el test
compara de verdad. No hace falta tocar el código del test.

**Importante — por qué las ausencias de Carla y Diego NO cambian su
`salario_bruto`**: en el código actual, una ausencia (con o sin goce de
salario) no descuenta nada del movimiento de planilla — solo afecta la
provisión de vacaciones (`vacaciones_service`). Por eso ambas comparten el
mismo bloque `quincena_base_800`, y lo único que realmente distingue su
ausencia médica (`enfermedad_dentro_fondo`, exenta siempre, Art. 208 CT) de
la injustificada (siempre descuenta) es la provisión de vacaciones — cubierto
por `test_diego_pierde_mas_dias_que_carla_en_el_mismo_rango`, que además es
puramente comparativo y **no** depende de `ESPERADOS` (corre siempre, incluso
sin fixture validado).

## Cómo agregar un caso de regresión nuevo cuando cambie una tasa legal

Cuando cambie una tasa (ej. CSS patronal 13.25% → 14.25% en marzo de 2027,
o una tabla de ISR nueva), **no** se edita este escenario — las tasas viejas
siguen siendo válidas para las fechas viejas y esta suite debe seguir
probándolas tal cual. En vez de eso:

1. Confirmar que la tasa nueva ya está sembrada en la BD vía migración
   (`tasas_vigentes`, `tramos_isr`, `tasas_riesgo_profesional`,
   `salario_minimo_vigente` — nunca hardcodeada en Python). La suite de
   test corre `alembic upgrade head` sola contra `nomina_test`
   (`tests/conftest.py::_preparar_base_de_datos`), así que si la migración
   ya existe, la tasa nueva está disponible automáticamente para cualquier
   fecha dentro de su rango de vigencia.
2. Copiar `fixtures_trimestre.py` y `test_trimestre_completo.py` a un par
   nuevo (ej. `fixtures_trimestre_2027.py` / `test_trimestre_2027.py`) con
   fechas dentro de la vigencia de la tasa nueva — mismo patrón, mismos 5
   roles de empleado si aplican, mismo `ESPERADOS` en `None` hasta llenarlo.
3. Pedirle al contador el cálculo a mano para esa ventana específica —
   **nunca reusar** un número de `fixtures_trimestre.py` (tasa vieja) para
   una fecha que cae bajo la tasa nueva, aunque el salario sea el mismo.

## Estado de validación

⚠️ **Ningún valor de `ESPERADOS` ha sido validado contra un contador
todavía** (2026-08-17, apertura de la Fase 17). Hasta que se llenen, el
sistema **no** debe considerarse verificado en producción solo por esta
suite — solo confirma que el flujo end-to-end no rompe.

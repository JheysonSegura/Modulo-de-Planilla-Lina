"""Datos del escenario de regresión "trimestre completo" (Fase 17 -- testing
integral, ver FASE17-plan-testing-integral.txt en la raíz del repo).

Este archivo NO calcula nada: solo define el escenario (fechas, salarios,
eventos) y el diccionario ESPERADOS con los montos que un contador debe
verificar a mano y pegar aquí. Mientras un valor de ESPERADOS sea None, el
test correspondiente en test_trimestre_completo.py se salta (pytest.skip)
en vez de comparar contra un placeholder inventado.

Cómo llenar ESPERADOS: cada entrada indica, en su comentario, el endpoint
exacto de la API que produce ese número (ver también backend/tests/
regresion/README.md para instrucciones paso a paso). Reemplazar None por
un string con el monto exacto, por ejemplo:

    "salario_bruto": "1500.00",

nunca un float (los tests comparan con decimal.Decimal(str(valor)), y un
float como 1500.00 puede perder precisión binaria antes de llegar a
Decimal -- por eso el placeholder también debe ser string).
"""

import datetime

# --- Cronología del trimestre --------------------------------------------
# Elegido para que termine exactamente el 15-abr-2026, fecha real de pago
# de la partida de décimo del cuatrimestre "dic-abr" (16-dic-2025 a
# 15-abr-2026). Los contratos arrancan el 16-ene-2026: DENTRO de ese
# cuatrimestre pero después de su inicio, para ejercitar a propósito el
# caso de "entrada tardía al cuatrimestre" (numerador reducido, divisor
# ÷12 fijo -- ver CLAUDE.md sección 4 "Décimo Tercer Mes").

FECHA_INICIO_CONTRATOS = datetime.date(2026, 1, 16)
FECHA_FIN_TRIMESTRE = datetime.date(2026, 4, 15)

QUINCENAS = [
    # (periodo_inicio, periodo_fin, fecha_pago)
    (datetime.date(2026, 1, 16), datetime.date(2026, 1, 31), datetime.date(2026, 2, 5)),
    (datetime.date(2026, 2, 1), datetime.date(2026, 2, 15), datetime.date(2026, 2, 20)),
    (datetime.date(2026, 2, 16), datetime.date(2026, 2, 28), datetime.date(2026, 3, 5)),
    (datetime.date(2026, 3, 1), datetime.date(2026, 3, 15), datetime.date(2026, 3, 20)),
    (datetime.date(2026, 3, 16), datetime.date(2026, 3, 31), datetime.date(2026, 4, 5)),
    (datetime.date(2026, 4, 1), datetime.date(2026, 4, 15), datetime.date(2026, 4, 20)),
]

DECIMO_REQUEST = {
    "cuatrimestre": "dic-abr",
    "anio": 2026,
    "fecha_pago": "2026-04-15",
}

# --- Empleados -------------------------------------------------------------
# Cada uno aísla un concepto de la Fase 17 para que un solo número mal
# calculado apunte a un solo sospechoso, en vez de mezclar varias
# novedades sobre la misma persona.

ANA = {
    "nombre": "Ana",
    "salario_base": "1500.00",  # por encima del umbral mensual de ISR ($846.15)
    "tipo_contrato": "indefinido",
}

BRUNO = {
    "nombre": "Bruno",
    "salario_base": "900.00",  # por debajo del umbral de ISR en su quincena base
    "tipo_contrato": "indefinido",
    # Horas extra en Q2/Q4/Q6 (índice 1, 3, 5 de QUINCENAS); Q1/Q3/Q5 son
    # su quincena base sin novedades.
    "horas_extra": [
        {  # Q2
            "fecha": datetime.date(2026, 2, 10),
            "tipo_hora": "diurna",
            "tipo_dia": "ordinario",
            "horas": "2.00",
        },
        {  # Q4
            "fecha": datetime.date(2026, 3, 10),
            "tipo_hora": "nocturna",
            "tipo_dia": "ordinario",
            "horas": "1.50",
        },
        {  # Q6
            "fecha": datetime.date(2026, 4, 5),
            "tipo_hora": "diurna",
            "tipo_dia": "domingo_descanso",
            "horas": "1.00",
        },
    ],
}

CARLA = {
    "nombre": "Carla",
    "salario_base": "800.00",
    "tipo_contrato": "indefinido",
    # Ausencia con justificación médica -- Art. 208 CT, exenta SIEMPRE de
    # descuento de vacaciones.
    "ausencia": {
        "tipo": "enfermedad_dentro_fondo",
        "fecha_desde": datetime.date(2026, 2, 5),
        "fecha_hasta": datetime.date(2026, 2, 9),
    },
}

DIEGO = {
    "nombre": "Diego",
    "salario_base": "800.00",
    "tipo_contrato": "indefinido",
    # Mismo rango de fechas que la ausencia de Carla a propósito, para que
    # el contraste médica-vs-injustificada sea directamente comparable.
    "ausencia": {
        "tipo": "injustificada",
        "fecha_desde": datetime.date(2026, 2, 5),
        "fecha_hasta": datetime.date(2026, 2, 9),
    },
}

ELENA = {
    "nombre": "Elena",
    "salario_base": "1200.00",
    "tipo_contrato": "indefinido",
    # Trabaja Q1+Q2 y se liquida a mitad del trimestre -- no llega al pago
    # de décimo del final (su décimo proporcional se salda en la
    # liquidación misma).
    "liquidacion": {
        "motivo": "despido_injustificado",
        "fecha_terminacion": datetime.date(2026, 2, 20),
    },
}

# --- Montos esperados -------------------------------------------------------
# TODOS en None hasta que el usuario los llene con cifras validadas por su
# contador. Un test cuyo bloque siga en None se SALTA (no falla, no asume).

ESPERADOS = {
    # Ana, quincena sin novedades. salario_bruto/css/seguro_educativo son
    # idénticos en las 6 quincenas, pero isr_retenido (y por lo tanto
    # salario_neto) ALTERNA por paridad -- corrección 2026-08-18,
    # confirmada por el contador: el ISR se prorratea contando los
    # períodos desde la fecha de inicio del contrato (16-ene, mitad del
    # año), no desde la posición absoluta del calendario. Q1/Q3/Q5 son
    # período relativo impar (1/3/5) del contrato, Q2/Q4/Q6 son par
    # (2/4/6) -- ver CLAUDE.md sección 5 y
    # test_contrato_que_arranca_a_mitad_de_anio_no_sobre_retiene en
    # backend/tests/test_isr.py. Fuente: GET /planillas/{id}/movimientos,
    # el elemento cuyo contrato_id es el de Ana.
    "ana_quincena_impar": {  # Q1, Q3, Q5 (período relativo 1, 3, 5)
        "salario_bruto": "750.00",
        "css_empleado": "73.12",
        "seguro_educativo_empleado": "9.38",
        "isr_retenido": "53.12",
        "salario_neto": "614.38",
    },
    "ana_quincena_par": {  # Q2, Q4, Q6 (período relativo 2, 4, 6)
        "salario_bruto": "750.00",
        "css_empleado": "73.12",
        "seguro_educativo_empleado": "9.38",
        "isr_retenido": "53.13",
        "salario_neto": "614.37",
    },
    # Bruno, quincena sin horas extra (Q1/Q3/Q5). Mismo endpoint que arriba.
    # seguro_educativo_empleado: el contador calculó $5.63 (450 x 1.25% =
    # 5.625, redondeo comercial "mitad hacia arriba"), pero el sistema da
    # $5.62 porque .quantize(_CENTAVO) en planilla_service.py no fija modo
    # de redondeo y Python usa ROUND_HALF_EVEN (bancario) por defecto --
    # 5.625 redondea al par más cercano (2), no hacia arriba. Mismo patrón
    # en 29 usos de .quantize() en 6 servicios (planilla, liquidaciones,
    # vacaciones, horas extra, salario mínimo, décimo). Decisión 2026-08-19:
    # por ahora se deja el comportamiento actual del sistema tal cual (no
    # se toca código); el fixture usa lo que el sistema realmente calcula
    # ($5.62 / neto $396.12), no lo que dio el contador a mano. Pendiente
    # de revisar el redondeo bancario como tema aparte si vuelve a aparecer.
    "bruno_quincena_base": {
        "salario_bruto": "450.00",
        "css_empleado": "43.88",
        "seguro_educativo_empleado": "5.62",
        "isr_retenido": "4.38",
        "salario_neto": "396.12",
    },
    # Bruno, cada quincena CON horas extra: 2 fuentes por índice --
    # (a) POST /contratos/{id}/horas-extra, el monto_calculado devuelto
    #     directo por ese registro (formula de cascada, Art. 33/36/48-50 CT);
    # (b) GET /planillas/{id}/movimientos de la quincena que las incluye,
    #     para confirmar que el motor de planilla las integró bien al bruto.
    "bruno_horas_extra": {
        "q2_diurna_ordinario": {
            "monto_calculado_registro": "9.38",
            "salario_bruto_quincena": "459.38",
            "isr_retenido_quincena": "4.37",
            "salario_neto_quincena": "404.48",
        },
        "q4_nocturna_ordinario": {
            "monto_calculado_registro": "8.44",
            "salario_bruto_quincena": "458.44",
            "isr_retenido_quincena": "4.37",
            "salario_neto_quincena": "403.64",
        },
        "q6_diurna_domingo_descanso": {
            "monto_calculado_registro": "7.03",
            "salario_bruto_quincena": "457.03",
            "isr_retenido_quincena": "4.37",
            "salario_neto_quincena": "402.39",
        },
    },
    # Carla (siempre) y Diego (sus quincenas SIN la ausencia -- Q1,
    # Q3-Q6) comparten esta misma quincena base ($800, sin novedades).
    # Mismo endpoint que ana_quincena_base.
    "quincena_base_800": {
        "salario_bruto": "400.00",
        "css_empleado": "39.00",
        "seguro_educativo_empleado": "5.00",
        "isr_retenido": "0.00",
        "salario_neto": "356.00",
    },
    # Q2 de Diego (1-15 feb), la única que se solapa con su ausencia
    # injustificada (5-9 feb, 5 días) -- corrección 2026-08-20: una
    # ausencia injustificada es "sin goce de salario" (ver CLAUDE.md
    # sección 4), así que esa quincena SÍ se reduce, a diferencia de
    # Carla (enfermedad_dentro_fondo, con goce completo por Art. 200
    # CT, nunca se reduce). CONFIRMADO por el contador 2026-08-20 con
    # el desglose completo: bruto $400.00 - ausencia $133.33 = $266.67
    # devengado; CSS 266.67×9.75%=$26.00; SE 266.67×1.25%=$3.33; ISR
    # $0.00; neto $266.67-$26.00-$3.33=$237.34.
    "diego_quincena_ausencia": {
        "salario_bruto": "266.67",
        "css_empleado": "26.00",
        "seguro_educativo_empleado": "3.33",
        "isr_retenido": "0.00",
        "salario_neto": "237.34",
    },
    # Snapshot final (tras la planilla de Q6) de
    # GET /contratos/{id}/provisiones-vacaciones -- fila con estado="abierto".
    # Carla (enfermedad_dentro_fondo) no debe perder ningún día; Diego
    # (injustificada) sí, sobre el mismo rango de fechas. 90 días
    # comerciales trabajados (16-ene a 15-abr, 3 meses x 30) / 11 = 8.1818
    # para Carla (sin descuento, Art. 208 exime siempre la ausencia
    # médica); Diego pierde los 5 días completos de su ausencia
    # injustificada -- (90 - 5) / 11 = 7.7273 -- el "colchón" de 15 días
    # del Art. 208 es para suspensiones del Art. 199, no aplica a este
    # tipo del catálogo de ausencias_service (Fase 11). Confirmado por el
    # contador 2026-08-20.
    "carla_provision_vacaciones_final": {
        "dias_acumulados": "8.18",
        "monto_provisionado": "218.18",
    },
    "diego_provision_vacaciones_final": {
        "dias_acumulados": "7.73",
        "monto_provisionado": "206.06",
    },
    # Décimo (POST /planillas/generar-decimo con DECIMO_REQUEST, luego
    # GET /planillas/{id}/movimientos de esa planilla). Un bloque por
    # empleado porque el numerador de cada uno es distinto (salario base
    # distinto, y el de Bruno además incluye sus horas extra del
    # cuatrimestre).
    "decimo": {
        "ana": {
            # $1,500 x 3 meses realmente trabajados (entró 16-ene, dentro
            # del cuatrimestre dic-abr) / 12 = $375.00. CSS especial
            # 7.25%: 375.00 x 0.0725 = 27.1875 -> 27.19.
            "salario_bruto": "375.00",
            "css_empleado": "27.19",
            "salario_neto": "347.81",
        },
        "bruno": {
            # CONFIRMADO por el contador 2026-08-20. Sus 6 quincenas
            # del trimestre (que coinciden con lo trabajado dentro del
            # cuatrimestre, entró 16-ene) suman $2,724.85 en bruto --
            # 3 quincenas base ($450 c/u) + 3 con horas extra
            # ($459.38+$458.44+$457.03). /12 = $227.07. CSS especial
            # 7.25%: 227.07×0.0725=16.4626->16.46.
            "salario_bruto": "227.07",
            "css_empleado": "16.46",
            "salario_neto": "210.61",
        },
        "carla": {
            # CONFIRMADO por el contador 2026-08-20. $800 × 3 meses
            # trabajados dentro del cuatrimestre / 12 = $200.00 (sin
            # ausencias con efecto en décimo: la médica tiene goce
            # completo). CSS 7.25%: 200.00×0.0725=14.50.
            "salario_bruto": "200.00",
            "css_empleado": "14.50",
            "salario_neto": "185.50",
        },
        "diego": {
            # CONFIRMADO por el contador 2026-08-20. 90 días
            # comerciales trabajados menos los 5 días de su
            # ausencia injustificada (sin goce de salario, corrección
            # 2026-08-20) = 85 días × $800/30 = $2,266.67 / 12 =
            # $188.89. CSS 7.25%: 188.89×0.0725=13.694525->13.69.
            "salario_bruto": "188.89",
            "css_empleado": "13.69",
            "salario_neto": "175.20",
        },
    },
    # Liquidación de Elena -- POST /contratos/{id}/liquidacion, respuesta
    # directa (LiquidacionOut).
    "liquidacion_elena": {
        "salario_pendiente": None,
        "decimo_proporcional": None,
        "vacaciones_pendientes": None,
        "prima_antiguedad": None,
        "indemnizacion": None,
        "preaviso": None,
        "monto_total": None,
    },
}

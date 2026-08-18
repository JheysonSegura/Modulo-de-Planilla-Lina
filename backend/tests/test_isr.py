import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Método confirmado por el contador el 2026-08-04 (ver CLAUDE.md
# sección 5 y FASE7-plan-isr.txt): renta bruta anual = salario_mensual
# x 13 (12 meses + décimo, sembrado como confirmado en la migración
# 0015_seed_decimo_isr), sin restar CSS/SE de esa base -- el excedente
# sobre $11,000 se grava directo con la tasa marginal del tramo.
# Caso de verificación del contador: $2,500/mes -> $32,500 bruto anual
# -> $21,500 excedente -> 15% -> $3,225.00/año -> $268.75/mes.


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> dict:
    # salario_minimo_vigente es global y sin rollback entre tests (ver
    # nota en test_horas_extra.py / test_planillas.py): se siembra
    # bajo con limpiar=True para no depender de lo que haya dejado
    # otro test, ni bloquear los salarios altos usados aquí (hasta
    # $6,000/mes para el tramo del 25%).
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)

    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _crear_empleado_con_contrato(client, headers, salario_base, fecha_inicio=datetime.date(2025, 1, 1)):
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": f"Empleado {_sufijo()}"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Prueba ISR",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": str(salario_base),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _generar_planilla(client, headers, tipo, periodo_inicio, periodo_fin):
    return client.post(
        "/planillas/generar",
        json={
            "tipo": tipo,
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )


def _unico_movimiento(client, headers, planilla_id):
    resp = client.get(f"/planillas/{planilla_id}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimientos = resp.json()
    assert len(movimientos) == 1
    return movimientos[0]


def test_empleado_exento_bajo_11000_anuales(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "800.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    # bruto anual con décimo: 800*13=10400 <= 11000 -> tramo exento
    assert decimal.Decimal(str(mov["isr_renta_anual_proyectada"])) == decimal.Decimal("10400.00")
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("0.00")
    assert mov["isr_numero_periodo_anio"] == 1
    assert mov["isr_periodos_restantes_anio"] == 12
    # Confirmado por el contador (migración 0015): el décimo se
    # integra a la base, sembrado como parámetro nacional vigente.
    assert mov["isr_decimo_tratamiento"] == "integrado"


def test_empleado_en_tramo_15_por_ciento(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "2000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    # bruto anual con décimo: 2000*13=26000 -> impuesto=(26000-11000)*0.15=2250.00 -> /12=187.50
    assert decimal.Decimal(str(mov["isr_renta_anual_proyectada"])) == decimal.Decimal("26000.00")
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("2250.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("187.50")
    assert mov["isr_decimo_tratamiento"] == "integrado"


def test_empleado_en_tramo_25_por_ciento(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "6000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    # bruto anual con décimo: 6000*13=78000 -> impuesto=5850+(78000-50000)*0.25=12850.00 -> /12=1070.83
    assert decimal.Decimal(str(mov["isr_renta_anual_proyectada"])) == decimal.Decimal("78000.00")
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("12850.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("1070.83")


def test_caso_verificado_por_el_contador_2500_mensual(client, db):
    """Caso exacto que el contador validó a mano el 2026-08-04:
    $2,500/mes -> $32,500 bruto anual con décimo -> $21,500 excedente
    sobre $11,000 -> 15% -> $3,225.00/año -> $268.75/mes."""
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "2500.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    assert decimal.Decimal(str(mov["isr_renta_anual_proyectada"])) == decimal.Decimal("32500.00")
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("3225.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("268.75")


def test_cambio_de_salario_a_mitad_de_anio_reconcilia_contra_lo_ya_retenido(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, "3000.00")

    resp_enero = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp_enero.status_code == 201, resp_enero.text
    mov_enero = _unico_movimiento(client, headers, resp_enero.json()["id"])
    # bruto anual con décimo: 3000*13=39000 -> impuesto=(39000-11000)*0.15=4200.00 -> /12=350.00
    assert decimal.Decimal(str(mov_enero["isr_impuesto_anual_proyectado"])) == decimal.Decimal(
        "4200.00"
    )
    assert decimal.Decimal(str(mov_enero["isr_retenido"])) == decimal.Decimal("350.00")

    resp_cambio = client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "5000.00", "fecha_vigencia_desde": "2025-02-01"},
        headers=headers,
    )
    assert resp_cambio.status_code == 201, resp_cambio.text

    resp_febrero = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 2, 1), datetime.date(2025, 2, 28)
    )
    assert resp_febrero.status_code == 201, resp_febrero.text
    mov_febrero = _unico_movimiento(client, headers, resp_febrero.json()["id"])

    # bruto anual con décimo: 5000*13=65000 -> impuesto=5850+(65000-50000)*0.25=9600.00
    assert decimal.Decimal(str(mov_febrero["isr_impuesto_anual_proyectado"])) == decimal.Decimal(
        "9600.00"
    )
    assert mov_febrero["isr_numero_periodo_anio"] == 2
    assert mov_febrero["isr_periodos_restantes_anio"] == 11
    # Ajuste progresivo: (9600.00 - 350.00 ya retenido en enero) / 11 = 840.91,
    # NO 9600.00/12 (eso ignoraría lo ya retenido y sub-retendría el año).
    assert decimal.Decimal(str(mov_febrero["isr_retenido"])) == decimal.Decimal("840.91")


def test_contrato_que_arranca_a_mitad_de_anio_no_sobre_retiene(client, db):
    """Corrección 2026-08-18, confirmada por el contador: el período de
    retención de un contrato debe contarse desde su propio primer pago
    dentro del año fiscal, no desde la posición absoluta en el
    calendario. Antes de esta corrección, un contrato que arranca el
    16-ene (calendario-período 2 de 24 quincenas) heredaba
    periodos_restantes=23 en su primera quincena -- como si el período
    1 ya se le hubiera consumido sin haber trabajado ahí -- y
    sobre-retenía ($55.43/$55.44 en vez de $53.12/$53.13).

    Caso: $1,500/mes, contrato arranca 2025-01-16 (quincena 16-31 ene =
    calendario-período 2). Bruto anual con décimo: 1500*13=19500 ->
    impuesto=(19500-11000)*0.15=1275.00/año. Con el fix, la primera
    quincena del contrato debe valer período relativo 1 de 24 (24
    cuotas completas por delante), no período 2 de 24."""
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(
        client, headers, "1500.00", fecha_inicio=datetime.date(2025, 1, 16)
    )

    resp_q1 = _generar_planilla(
        client, headers, "quincenal", datetime.date(2025, 1, 16), datetime.date(2025, 1, 31)
    )
    assert resp_q1.status_code == 201, resp_q1.text
    mov_q1 = _unico_movimiento(client, headers, resp_q1.json()["id"])

    assert decimal.Decimal(str(mov_q1["isr_impuesto_anual_proyectado"])) == decimal.Decimal(
        "1275.00"
    )
    assert mov_q1["isr_numero_periodo_anio"] == 1
    assert mov_q1["isr_periodos_restantes_anio"] == 24
    # 1275.00 / 24 = 53.125 -> redondeo half-even -> 53.12 (no 55.43,
    # que es lo que daba antes de la corrección)
    assert decimal.Decimal(str(mov_q1["isr_retenido"])) == decimal.Decimal("53.12")

    resp_q2 = _generar_planilla(
        client, headers, "quincenal", datetime.date(2025, 2, 1), datetime.date(2025, 2, 15)
    )
    assert resp_q2.status_code == 201, resp_q2.text
    mov_q2 = _unico_movimiento(client, headers, resp_q2.json()["id"])

    assert mov_q2["isr_numero_periodo_anio"] == 2
    assert mov_q2["isr_periodos_restantes_anio"] == 23
    # (1275.00 - 53.12 ya retenido) / 23 = 53.1252... -> 53.13
    assert decimal.Decimal(str(mov_q2["isr_retenido"])) == decimal.Decimal("53.13")


def test_periodo_no_alineado_a_mes_o_quincena_estandar_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "2000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 3, 5), datetime.date(2025, 3, 20)
    )
    assert resp.status_code == 422, resp.text
    assert "período fiscal" in resp.json()["detail"]

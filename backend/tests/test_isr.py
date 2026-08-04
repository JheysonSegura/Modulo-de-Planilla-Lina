import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular


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

    # bruto anual 800*12=9600, neto tras CSS/SE (11%) = 8544 -> tramo exento
    assert decimal.Decimal(str(mov["isr_renta_anual_proyectada"])) == decimal.Decimal("9600.00")
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("0.00")
    assert mov["isr_numero_periodo_anio"] == 1
    assert mov["isr_periodos_restantes_anio"] == 12
    # Sin parametros_isr sembrado (estado normal de esta fase): nunca
    # se confunde con una decisión legal ya tomada ('exento').
    assert mov["isr_decimo_tratamiento"] == "no_configurado"


def test_empleado_en_tramo_15_por_ciento(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "2000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    # bruto 24000, neto 21360 -> impuesto=(21360-11000)*0.15=1554.00 -> /12=129.50
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("1554.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("129.50")


def test_empleado_en_tramo_25_por_ciento(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "6000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp.status_code == 201, resp.text
    mov = _unico_movimiento(client, headers, resp.json()["id"])

    # bruto 72000, neto 64080 -> impuesto=5850+(64080-50000)*0.25=9370.00 -> /12=780.83
    assert decimal.Decimal(str(mov["isr_impuesto_anual_proyectado"])) == decimal.Decimal("9370.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("780.83")


def test_cambio_de_salario_a_mitad_de_anio_reconcilia_contra_lo_ya_retenido(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, "3000.00")

    resp_enero = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    assert resp_enero.status_code == 201, resp_enero.text
    mov_enero = _unico_movimiento(client, headers, resp_enero.json()["id"])
    # bruto 36000, neto 32040 -> impuesto=(32040-11000)*0.15=3156.00 -> /12=263.00
    assert decimal.Decimal(str(mov_enero["isr_impuesto_anual_proyectado"])) == decimal.Decimal(
        "3156.00"
    )
    assert decimal.Decimal(str(mov_enero["isr_retenido"])) == decimal.Decimal("263.00")

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

    # bruto 60000, neto 53400 -> impuesto=5850+(53400-50000)*0.25=6700.00
    assert decimal.Decimal(str(mov_febrero["isr_impuesto_anual_proyectado"])) == decimal.Decimal(
        "6700.00"
    )
    assert mov_febrero["isr_numero_periodo_anio"] == 2
    assert mov_febrero["isr_periodos_restantes_anio"] == 11
    # Ajuste progresivo: (6700.00 - 263.00 ya retenido en enero) / 11 = 585.18,
    # NO 6700.00/12 (eso ignoraría lo ya retenido y sub-retendría el año).
    assert decimal.Decimal(str(mov_febrero["isr_retenido"])) == decimal.Decimal("585.18")


def test_periodo_no_alineado_a_mes_o_quincena_estandar_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, "2000.00")

    resp = _generar_planilla(
        client, headers, "mensual", datetime.date(2025, 3, 5), datetime.date(2025, 3, 20)
    )
    assert resp.status_code == 422, resp.text
    assert "período fiscal" in resp.json()["detail"]

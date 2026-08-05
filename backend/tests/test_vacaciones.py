import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Código de Trabajo, Art. 54.1: vacaciones = (días trabajados / 11) x
# salario_diario (salario_diario = salario_mensual/30, mes comercial).
# Salario 900.00/mes elegido para que salario_diario=30.00 exacto y las
# cuentas a mano sean simples -- mismo criterio que test_decimo.py.
SALARIO = "900.00"


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> dict:
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _crear_empleado_con_contrato(client, headers, fecha_inicio, salario_base=SALARIO):
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
            "cargo": "Prueba vacaciones",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": str(salario_base),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _generar_planilla(client, headers, tipo, periodo_inicio, periodo_fin):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": tipo,
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _provisiones(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/provisiones-vacaciones", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _provision_abierta(client, headers, contrato_id):
    return next(p for p in _provisiones(client, headers, contrato_id) if p["estado"] == "abierto")


def _registrar_vacacion_tomada(client, headers, contrato_id, fecha, dias):
    return client.post(
        f"/contratos/{contrato_id}/vacaciones-tomadas",
        json={"fecha": fecha.isoformat(), "dias": str(dias)},
        headers=headers,
    )


def test_dias_acumulados_para_137_dias_trabajados(client, db):
    headers = _preparar_empresa(db, client)
    # 2024-12-15 a 2025-04-30 inclusive = 137 días exactos (17 días de
    # diciembre + 31 enero + 28 febrero + 31 marzo + 30 abril = 137).
    # periodo_fin cae en un fin de mes calendario válido (el motor de
    # planilla exige mes completo o quincena estándar para el ISR).
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    prov = _provision_abierta(client, headers, contrato_id)
    # 137/11 = 12.454545... -> 12.45 días
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.45")
    # 137/11 * 30.00 = 373.636363... -> 373.64
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("373.64")
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("12.45")
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("0.00")
    assert prov["fecha_inicio_periodo"] == "2024-12-15"


def test_provision_se_recalcula_completo_en_cada_planilla_no_se_acumula(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    # Enero completo: 31 días -> 31/11=2.818181... -> 2.82 días;
    # 31/11*30.00=84.5454... -> 84.55.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    prov = _provision_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("2.82")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("84.55")

    # Enero+Febrero: 59 días -> 59/11=5.363636... -> 5.36 días;
    # 59/11*30.00=160.9090... -> 160.91. Verifica que se RECALCULA
    # completo desde el inicio del período (no se suma 84.55 + lo de
    # febrero por separado, lo que daría un número distinto por el
    # redondeo acumulado).
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 2, 1), datetime.date(2025, 2, 28))
    prov = _provision_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("5.36")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("160.91")


def test_registrar_vacacion_tomada_reduce_el_saldo(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))

    # 2024-12-15 a 2025-04-30 = 137 días, ver test anterior.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
    prov = _provision_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("12.45")

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 4, 30), "5")
    assert resp.status_code == 201, resp.text
    prov = resp.json()
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("5.00")
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.45")
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("7.45")
    # 373.636363... - 5*30.00 = 223.636363... -> 223.64
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("223.64")

    # Una segunda vacación tomada sigue reduciendo desde el saldo ya
    # descontado, no desde el acumulado original.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 4, 30), "7")
    assert resp.status_code == 201, resp.text
    prov = resp.json()
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("12.00")
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("0.45")


def test_no_se_puede_tomar_mas_dias_de_los_disponibles(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))

    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    # Saldo disponible es 12.45 -> pedir 13 debe rechazarse.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 4, 30), "13")
    assert resp.status_code == 422, resp.text
    assert "disponibles" in resp.json()["detail"].lower()

    # El saldo no debe haber cambiado tras el intento rechazado.
    prov = _provision_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("0.00")


def test_dias_tomados_debe_ser_mayor_que_cero(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 4, 30), "0")
    assert resp.status_code == 422, resp.text

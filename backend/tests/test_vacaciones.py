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


def _acumular_periodo(client, headers, contrato_id, fecha_acuerdo, notificado=False):
    return client.post(
        f"/contratos/{contrato_id}/vacaciones-acumular",
        json={
            "fecha_acuerdo": fecha_acuerdo.isoformat(),
            "notificado_autoridad_trabajo": notificado,
        },
        headers=headers,
    )


def _provision_acumulada(client, headers, contrato_id):
    return next(p for p in _provisiones(client, headers, contrato_id) if p["estado"] == "acumulado")


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


# --- Fase 12: acumulación de hasta 2 períodos (Art. 59 CT) ---
# 2024-12-15 a 2025-05-31 = 168 días (17 dic + 31 ene + 28 feb + 31 mar
# + 30 abr + 31 may) -> 168/11=15.272727... -> 15.27 días;
# 168/11*30.00=458.1818... -> 458.18. Es el "saldo con al menos 15
# días" que exige el Art. 59 para poder acumular.


def test_acumular_con_menos_de_15_dias_de_saldo_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    # 137 días -> 12.45 días, por debajo del mínimo de 15.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    resp = _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 4, 30))
    assert resp.status_code == 422, resp.text
    assert "15" in resp.json()["detail"]


def test_acumular_periodo_congela_el_actual_y_abre_uno_nuevo(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))

    resp = _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31), notificado=True)
    assert resp.status_code == 201, resp.text
    nuevo = resp.json()
    assert nuevo["estado"] == "abierto"
    assert nuevo["fecha_inicio_periodo"] == "2025-06-01"
    assert decimal.Decimal(str(nuevo["dias_acumulados"])) == decimal.Decimal("0.00")

    acumulado = _provision_acumulada(client, headers, contrato_id)
    assert decimal.Decimal(str(acumulado["dias_acumulados"])) == decimal.Decimal("15.27")
    assert decimal.Decimal(str(acumulado["monto_provisionado"])) == decimal.Decimal("458.18")
    assert acumulado["notificado_autoridad_trabajo"] is True

    provisiones = _provisiones(client, headers, contrato_id)
    assert len(provisiones) == 2


def test_acumular_un_tercer_periodo_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))

    primera = _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31))
    assert primera.status_code == 201, primera.text

    segunda = _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 6, 30))
    assert segunda.status_code == 409, segunda.text


def test_vacacion_tomada_descuenta_primero_del_periodo_acumulado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))
    _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31))

    # 10 días caben enteros dentro del saldo del período 'acumulado'
    # (15.27) -- el 'abierto' (recién creado, 2025-06-01) no se toca.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 6, 1), "10")
    assert resp.status_code == 201, resp.text
    tocado = resp.json()
    assert tocado["estado"] == "acumulado"
    assert decimal.Decimal(str(tocado["dias_gozados"])) == decimal.Decimal("10.00")
    # 458.18 - 10*30.00 = 158.18
    assert decimal.Decimal(str(tocado["monto_provisionado"])) == decimal.Decimal("158.18")

    provisiones = _provisiones(client, headers, contrato_id)
    abierto = next(p for p in provisiones if p["estado"] == "abierto")
    assert decimal.Decimal(str(abierto["dias_gozados"])) == decimal.Decimal("0.00")


def test_vacacion_tomada_consume_el_abierto_cuando_el_acumulado_no_alcanza(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))
    _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31))

    # El 'abierto' recién creado (fecha_inicio_periodo=2025-06-01) ya
    # acumuló 1 día al 2025-06-01 (mismo día inclusive): 1/11=0.09 días,
    # 1/11*30.00=2.73. saldo total = 15.27 (acumulado) + 0.09 (abierto)
    # = 15.36 -- pedir 15.30 agota el acumulado (15.27) y toma 0.03 del
    # abierto.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 6, 1), "15.30")
    assert resp.status_code == 201, resp.text
    tocado = resp.json()
    assert tocado["estado"] == "abierto"
    assert decimal.Decimal(str(tocado["dias_gozados"])) == decimal.Decimal("0.03")
    # 2.73 - 0.03*30.00 = 1.83
    assert decimal.Decimal(str(tocado["monto_provisionado"])) == decimal.Decimal("1.83")

    acumulado = _provision_acumulada(client, headers, contrato_id)
    assert decimal.Decimal(str(acumulado["dias_gozados"])) == decimal.Decimal("15.27")
    assert decimal.Decimal(str(acumulado["saldo_disponible"])) == decimal.Decimal("0.00")


def test_periodo_acumulado_no_crece_en_planillas_posteriores(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))
    _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31))

    # Una planilla posterior recalcula el 'abierto' (30 días de junio ->
    # 30/11=2.7272... -> 2.73 días, 30/11*30.00=81.8181... -> 81.82) pero
    # NO toca el 'acumulado', que queda congelado en lo que tenía.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))

    provisiones = _provisiones(client, headers, contrato_id)
    abierto = next(p for p in provisiones if p["estado"] == "abierto")
    assert decimal.Decimal(str(abierto["dias_acumulados"])) == decimal.Decimal("2.73")
    assert decimal.Decimal(str(abierto["monto_provisionado"])) == decimal.Decimal("81.82")

    acumulado = _provision_acumulada(client, headers, contrato_id)
    assert decimal.Decimal(str(acumulado["dias_acumulados"])) == decimal.Decimal("15.27")
    assert decimal.Decimal(str(acumulado["monto_provisionado"])) == decimal.Decimal("458.18")

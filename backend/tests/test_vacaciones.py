import calendar
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


def _vacaciones_tomadas(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/vacaciones-tomadas", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


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

    # 2026-10-27: el descanso arranca el 1-may (no el 30-abr) porque ya no
    # se permite registrar vacaciones sobre días que paga una planilla
    # regular (abril ya generada) -- habría doble pago. El saldo se
    # recalcula a la fecha de inicio: 138 días -> 138/11=12.5454... -> 12.55.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 5, 1), "5")
    assert resp.status_code == 201, resp.text
    prov = resp.json()
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("5.00")
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.55")
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("7.55")
    # 376.363636... - 5*30.00 = 226.363636... -> 226.36
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("226.36")

    # Una segunda vacación tomada sigue reduciendo desde el saldo ya
    # descontado, no desde el acumulado original. Arranca el 6-may, al día
    # siguiente de terminar la primera (1 al 5-may): 143 días -> 13.00.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 5, 6), "7")
    assert resp.status_code == 201, resp.text
    prov = resp.json()
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("12.00")
    assert decimal.Decimal(str(prov["saldo_disponible"])) == decimal.Decimal("1.00")


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


def test_dias_tomados_rechaza_decimales(client, db):
    """2026-08-07: días tomados debe ser siempre un número entero -- un
    trabajador toma días de calendario completos, nunca una fracción de
    día (a diferencia de días acumulados, que sigue siendo decimal por
    diseño, Art. 54.1 CT). Un decimal como "1.01" ya no se acepta."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 4, 30), "1.01")
    assert resp.status_code == 422, resp.text

    # El saldo no debe haber cambiado tras el intento rechazado.
    prov = _provision_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_gozados"])) == decimal.Decimal("0.00")


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

    # El 'abierto' recién creado (fecha_inicio_periodo=2025-06-01) acumuló
    # 10 días al 2025-06-10 (ambos extremos inclusive): 10/11=0.909090...
    # -> 0.91 días, 0.909090...*30.00=27.2727... -> 27.27. saldo total =
    # 15.27 (acumulado) + 0.91 (abierto) = 16.18 -- pedir 16 (entero,
    # 2026-08-07: dias_tomados ya no acepta decimales) agota el
    # acumulado (15.27) y toca 0.73 del abierto. La fracción que queda
    # por período es esperada (ver docstring de registrar_vacacion_tomada
    # sobre el límite conocido de Fase 12 con tomas enteras que cruzan
    # períodos), aunque el total pedido sí fue un entero.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 6, 10), "16")
    assert resp.status_code == 201, resp.text
    tocado = resp.json()
    assert tocado["estado"] == "abierto"
    assert decimal.Decimal(str(tocado["dias_gozados"])) == decimal.Decimal("0.73")
    # 27.27 - 0.73*30.00 = 5.37
    assert decimal.Decimal(str(tocado["monto_provisionado"])) == decimal.Decimal("5.37")

    acumulado = _provision_acumulada(client, headers, contrato_id)
    assert decimal.Decimal(str(acumulado["dias_gozados"])) == decimal.Decimal("15.27")
    assert decimal.Decimal(str(acumulado["saldo_disponible"])) == decimal.Decimal("0.00")


def test_una_toma_dentro_de_un_solo_periodo_genera_un_evento(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 5, 1), "5")
    assert resp.status_code == 201, resp.text

    eventos = _vacaciones_tomadas(client, headers, contrato_id)
    assert len(eventos) == 1
    assert decimal.Decimal(str(eventos[0]["dias_tomados"])) == decimal.Decimal("5.00")
    # 5 días * valor_dia 30.00 = 150.00
    assert decimal.Decimal(str(eventos[0]["monto"])) == decimal.Decimal("150.00")

    # Una segunda toma (todavía dentro del mismo período 'abierto') es
    # un segundo evento independiente, no se acumula al primero.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 5, 6), "7")
    assert resp.status_code == 201, resp.text
    eventos = _vacaciones_tomadas(client, headers, contrato_id)
    assert len(eventos) == 2


def test_una_toma_que_cruza_acumulado_y_abierto_genera_dos_eventos(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))
    _acumular_periodo(client, headers, contrato_id, datetime.date(2025, 5, 31))

    # Mismo escenario que
    # test_vacacion_tomada_consume_el_abierto_cuando_el_acumulado_no_alcanza:
    # 16 días (entero) agota el 'acumulado' (15.27) y toca 0.73 del
    # 'abierto' en una sola llamada -> 2 filas de historial, una por
    # período.
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2025, 6, 10), "16")
    assert resp.status_code == 201, resp.text

    eventos = _vacaciones_tomadas(client, headers, contrato_id)
    assert len(eventos) == 2
    dias_por_evento = sorted(decimal.Decimal(str(e["dias_tomados"])) for e in eventos)
    assert dias_por_evento == [decimal.Decimal("0.73"), decimal.Decimal("15.27")]
    assert sum(dias_por_evento) == decimal.Decimal("16.00")


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


# --- Descuentos de ley en el pago de vacaciones (2026-10-23/27) ---
# Ver PLAN-vacaciones-descuentos.md. Cada toma genera su propia planilla
# tipo='vacaciones' con CSS/SE/ISR, y ese pago REEMPLAZA el salario de
# esos días en las quincenas regulares. ISR = impuesto anual proyectado
# ÷ 12 × días/30.


def _d(valor) -> decimal.Decimal:
    return decimal.Decimal(str(valor))


def _movimiento_unico(client, headers, planilla_id):
    resp = client.get(f"/planillas/{planilla_id}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimientos = resp.json()
    assert len(movimientos) == 1
    return movimientos[0]


def _planilla_de_vacaciones(client, headers, contrato_id):
    eventos = [e for e in _vacaciones_tomadas(client, headers, contrato_id) if not e["anulada"]]
    assert eventos, "la toma no generó eventos"
    return eventos[0]["planilla_id"]


def _quincena(client, headers, anio, mes, mitad):
    if mitad == 1:
        inicio, fin = datetime.date(anio, mes, 1), datetime.date(anio, mes, 15)
    else:
        ultimo = calendar.monthrange(anio, mes)[1]
        inicio, fin = datetime.date(anio, mes, 16), datetime.date(anio, mes, ultimo)
    planilla = _generar_planilla(client, headers, "quincenal", inicio, fin)
    return _movimiento_unico(client, headers, planilla["id"])


def test_caso_a_vacacion_de_30_dias_con_descuentos_y_quincenas_en_cero(client, db):
    """Caso A del plan: $2,500/mes, 30 días del 1 al 30-mar-2026.
    Bruto 2,500.00; CSS 9.75% = 243.75; SE 1.25% = 31.25; ISR =
    3,225.00/12 = 268.75 (mismo caso de verificación del contador, Fase 7)
    -> neto 1,956.25. Patronal: CSS 13.25% = 331.25, SE 1.5% = 37.50."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 1, 1), salario_base="2500.00"
    )
    for mes in (1, 2):
        for mitad in (1, 2):
            _quincena(client, headers, 2026, mes, mitad)

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 30)
    assert resp.status_code == 201, resp.text

    evento = _vacaciones_tomadas(client, headers, contrato_id)[0]
    assert evento["fecha_fin_goce"] == "2026-03-30"
    assert evento["planilla_estado"] == "borrador"
    assert _d(evento["salario_neto"]) == _d("1956.25")

    planilla = client.get(f"/planillas/{evento['planilla_id']}", headers=headers).json()
    assert planilla["tipo"] == "vacaciones"
    assert planilla["periodo_inicio"] == "2026-03-01"
    assert planilla["periodo_fin"] == "2026-03-30"
    # Art. 54.5 CT: por defecto 3 días antes del descanso.
    assert planilla["fecha_pago"] == "2026-02-26"

    mov = _movimiento_unico(client, headers, evento["planilla_id"])
    assert _d(mov["salario_bruto"]) == _d("2500.00")
    assert _d(mov["css_empleado"]) == _d("243.75")
    assert _d(mov["seguro_educativo_empleado"]) == _d("31.25")
    assert _d(mov["isr_retenido"]) == _d("268.75")
    assert _d(mov["salario_neto"]) == _d("1956.25")
    assert _d(mov["css_patronal"]) == _d("331.25")
    assert _d(mov["seguro_educativo_patronal"]) == _d("37.50")
    assert _d(mov["isr_impuesto_anual_proyectado"]) == _d("3225.00")

    # Las quincenas de marzo no vuelven a pagar los días de vacaciones. La
    # 1ª queda en cero; la 2ª paga solo el 31-mar, día en que la persona ya
    # regresó a trabajar (confirmado por el contador 2026-10-27): 2,500/30 =
    # 83.33. ISR: (3,225 - 537.50 de ene/feb - 268.75 de vacaciones) / 19
    # períodos restantes = 127.30... × 1/15 = 8.49.
    mov_q1 = _quincena(client, headers, 2026, 3, 1)
    assert _d(mov_q1["salario_bruto"]) == _d("0.00")
    assert _d(mov_q1["isr_retenido"]) == _d("0.00")
    mov_q2 = _quincena(client, headers, 2026, 3, 2)
    assert _d(mov_q2["salario_bruto"]) == _d("83.33")
    assert _d(mov_q2["isr_retenido"]) == _d("8.49")
    for mov_q in (mov_q1, mov_q2):
        codigos = [c["codigo"] for c in mov_q["conceptos_variables"]]
        assert "vacaciones_pagadas_aparte" in codigos

    # 1ª quincena de abril: ISR normal, la reconciliación anual cuadra
    # (3,225 - 537.50 - 268.75 - 8.49) / 18 = 133.903...
    mov_abril = _quincena(client, headers, 2026, 4, 1)
    assert _d(mov_abril["salario_bruto"]) == _d("1250.00")
    assert _d(mov_abril["isr_retenido"]) == _d("133.90")


def test_caso_b_quince_dias_equivale_a_una_quincena_normal(client, db):
    """Caso B del plan: $900/mes, 15 días del 1 al 15-mar-2026. Bruto
    450.00, CSS 43.88, SE 5.62, ISR 105.00/12 × 15/30 = 4.38 -> neto
    396.12, igual que la quincena base de Bruno (Fase 17)."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 15)
    assert resp.status_code == 201, resp.text

    mov = _movimiento_unico(client, headers, _planilla_de_vacaciones(client, headers, contrato_id))
    assert _d(mov["salario_bruto"]) == _d("450.00")
    assert _d(mov["css_empleado"]) == _d("43.88")
    assert _d(mov["seguro_educativo_empleado"]) == _d("5.62")
    assert _d(mov["isr_retenido"]) == _d("4.38")
    assert _d(mov["salario_neto"]) == _d("396.12")

    assert _d(_quincena(client, headers, 2026, 3, 1)["salario_bruto"]) == _d("0.00")
    assert _d(_quincena(client, headers, 2026, 3, 2)["salario_bruto"]) == _d("450.00")


def test_vacacion_que_cruza_quincenas_descuenta_solo_los_dias_de_cada_una(client, db):
    """Del 10-mar al 8-abr-2026 (30 días). 1ª de marzo: 6 días (10-15) ->
    450 - 180 = 270. 2ª de marzo: 16 días calendario (16-31) pero la
    quincena vale 15 comerciales -> tope 15 -> 0. 1ª de abril: 8 días ->
    450 - 240 = 210. (El día 31-mar queda como punto a confirmar con el
    contador, ver PLAN-vacaciones-descuentos.md.)"""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 10), 30)
    assert resp.status_code == 201, resp.text

    assert _d(_quincena(client, headers, 2026, 3, 1)["salario_bruto"]) == _d("270.00")
    assert _d(_quincena(client, headers, 2026, 3, 2)["salario_bruto"]) == _d("0.00")
    assert _d(_quincena(client, headers, 2026, 4, 1)["salario_bruto"]) == _d("210.00")


def test_vacacion_desde_el_1_de_febrero_no_paga_la_segunda_quincena_de_febrero(client, db):
    """Confirmado por el usuario 2026-10-27: sale el 1-feb-2026, 30 días
    calendario -> termina el 2-mar, regresa el 3-mar. La 2ª quincena de
    febrero (16-28, 13 días reales) vale 15 comerciales y está toda dentro
    del descanso -> 0, no 2 días. 1ª de marzo: solo del 3 al 15 ->
    450 - 2 × 30 = 390."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 2, 1), 30)
    assert resp.status_code == 201, resp.text
    assert _vacaciones_tomadas(client, headers, contrato_id)[0]["fecha_fin_goce"] == "2026-03-02"

    assert _d(_quincena(client, headers, 2026, 2, 1)["salario_bruto"]) == _d("0.00")
    assert _d(_quincena(client, headers, 2026, 2, 2)["salario_bruto"]) == _d("0.00")
    assert _d(_quincena(client, headers, 2026, 3, 1)["salario_bruto"]) == _d("390.00")


def test_vacacion_que_termina_a_mitad_de_quincena_paga_los_dias_trabajados_incluido_el_31(
    client, db
):
    """Del 20-feb al 21-mar-2026 (30 días), regresa el 22-mar. 2ª de
    febrero: vacaciones del 20 al 28 = 11 días comerciales -> paga 4 (16 al
    19) = 120. 2ª de marzo: trabaja del 22 al 31 = 10 días calendario; la
    cuenta comercial (15 - 6) daría 9, pero el 31 trabajado tras volver de
    vacaciones se paga (contador 2026-10-27) -> 10 × 30 = 300."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 2, 20), 30)
    assert resp.status_code == 201, resp.text

    assert _d(_quincena(client, headers, 2026, 2, 2)["salario_bruto"]) == _d("120.00")
    assert _d(_quincena(client, headers, 2026, 3, 1)["salario_bruto"]) == _d("0.00")
    assert _d(_quincena(client, headers, 2026, 3, 2)["salario_bruto"]) == _d("300.00")


def test_rechaza_vacacion_sobre_dias_que_ya_paga_una_planilla_regular(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _quincena(client, headers, 2026, 3, 1)

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 10), 10)
    assert resp.status_code == 422, resp.text
    assert "dos veces" in resp.json()["detail"]
    assert _vacaciones_tomadas(client, headers, contrato_id) == []
    prov = _provision_abierta(client, headers, contrato_id)
    assert _d(prov["dias_gozados"]) == _d("0.00")


def test_rechaza_vacacion_que_se_solapa_con_otra_vacacion(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 10)
    assert resp.status_code == 201, resp.text
    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 5), 5)
    assert resp.status_code == 422, resp.text


def test_anular_planilla_de_vacaciones_devuelve_los_dias_al_saldo(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 15)
    assert resp.status_code == 201, resp.text
    assert _d(resp.json()["dias_gozados"]) == _d("15.00")
    planilla_id = _planilla_de_vacaciones(client, headers, contrato_id)

    resp = client.post(f"/planillas/{planilla_id}/anular", headers=headers)
    assert resp.status_code == 200, resp.text

    prov = _provision_abierta(client, headers, contrato_id)
    assert _d(prov["dias_gozados"]) == _d("0.00")
    evento = _vacaciones_tomadas(client, headers, contrato_id)[0]
    assert evento["anulada"] is True
    assert evento["planilla_estado"] == "anulada"

    # Sin la planilla de vacaciones, la quincena vuelve a pagar completo.
    assert _d(_quincena(client, headers, 2026, 3, 1)["salario_bruto"]) == _d("450.00")


def test_no_se_anula_vacacion_ya_descontada_por_una_quincena(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 15)
    assert resp.status_code == 201, resp.text
    planilla_id = _planilla_de_vacaciones(client, headers, contrato_id)
    _quincena(client, headers, 2026, 3, 1)

    resp = client.post(f"/planillas/{planilla_id}/anular", headers=headers)
    assert resp.status_code == 409, resp.text
    prov = _provision_abierta(client, headers, contrato_id)
    assert _d(prov["dias_gozados"]) == _d("15.00")


def test_liquidacion_no_vuelve_a_pagar_dias_de_vacaciones(client, db):
    """Salario pendiente desde la última planilla regular (28-feb) hasta
    el 10-mar = 10 días, menos 5 días que ya pagó la planilla de
    vacaciones (1 al 5-mar) -> 5 × 30.00 = 150.00."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _quincena(client, headers, 2026, 2, 2)

    resp = _registrar_vacacion_tomada(client, headers, contrato_id, datetime.date(2026, 3, 1), 5)
    assert resp.status_code == 201, resp.text

    resp = client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={"motivo": "renuncia_voluntaria", "fecha_terminacion": "2026-03-10"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert _d(resp.json()["salario_pendiente"]) == _d("150.00")

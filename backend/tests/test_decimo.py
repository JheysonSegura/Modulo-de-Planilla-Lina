import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Fórmula CONFIRMADA por el contador el 2026-08-06 con caso numérico
# (corrige el método de la Fase 8): décimo = (ingresos brutos
# devengados en el cuatrimestre) / 12, contando el salario base en
# días "comerciales" (cualquier mes completo = 30 días, sin importar
# su largo real -- convención 30/360). Salario 900.00/mes elegido para
# que salario_diario=30.00 exacto y las cuentas a mano sean simples --
# ver FASE8-plan-decimo.txt para el desglose completo.
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
            "cargo": "Prueba decimo",
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


def _generar_pago_decimo(client, headers, cuatrimestre, anio, fecha_pago):
    return client.post(
        "/planillas/generar-decimo",
        json={"cuatrimestre": cuatrimestre, "anio": anio, "fecha_pago": fecha_pago.isoformat()},
        headers=headers,
    )


def _provisiones(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/provisiones-decimo", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _movimiento_de(movimientos, contrato_id):
    return next(m for m in movimientos if m["contrato_id"] == contrato_id)


def _registrar_ausencia(client, headers, contrato_id, tipo, fecha_desde, fecha_hasta):
    resp = client.post(
        f"/contratos/{contrato_id}/ausencias",
        json={
            "tipo": tipo,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_partidas_de_un_anio_completo_trabajado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 1, 1))

    # dic-abr 2025: cuatrimestre completo = 120 días comerciales
    # exactos (4 meses de 30, no 121 días reales de calendario) ->
    # 120*30.00/12=300.00
    resp = _generar_pago_decimo(client, headers, "dic-abr", 2025, datetime.date(2025, 4, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("300.00")

    # abr-ago 2025: cuatrimestre completo -> mismo cálculo, siempre 120
    # días comerciales sin importar cuál cuatrimestre sea -> 300.00
    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("300.00")

    # ago-dic 2025: mismo cálculo -> 300.00
    resp = _generar_pago_decimo(client, headers, "ago-dic", 2025, datetime.date(2025, 12, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("300.00")

    # CSS especial sobre el décimo (7.25%/10.75%), SE no aplica, ISR no
    # se duplica (ya prorrateado en los pagos regulares de Fase 7).
    assert decimal.Decimal(str(mov["css_empleado"])) == (
        decimal.Decimal("300.00") * decimal.Decimal("0.0725")
    ).quantize(decimal.Decimal("0.01"))
    assert decimal.Decimal(str(mov["seguro_educativo_empleado"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(mov["isr_retenido"])) == decimal.Decimal("0.00")


def test_ingreso_a_mitad_de_cuatrimestre_prorratea_por_dias(client, db):
    headers = _preparar_empresa(db, client)
    # Empieza el 1 de mayo, dentro del cuatrimestre abr-ago (16-abr a
    # 15-ago 2025): solo cuenta lo devengado desde el ingreso -- el
    # divisor sigue siendo 12 siempre (el contador confirmó "se divide
    # siempre entre 4, no importa la fecha de ingreso"), la fecha
    # tardía solo reduce la suma. 1-may a 15-ago = 105 días comerciales
    # (may=30 + jun=30 + jul=30 + ago1-15=15) -> 105*30.00=3150.00 / 12
    # = 262.50
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 5, 1))

    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("262.50")


def test_cambio_de_salario_a_mitad_de_cuatrimestre_calcula_por_segmento(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(
        client, headers, datetime.date(2024, 1, 1), salario_base="900.00"
    )
    resp = client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "1200.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    # abr-ago 2025 (16-abr a 15-ago): segmento a 900 (16-abr a 31-may,
    # días comerciales: abr16-30=15 + may completo=30 = 45) + segmento
    # a 1200 (1-jun a 15-ago, comerciales: jun=30+jul=30+ago1-15=15=75).
    # 45*30.00 + 75*40.00 = 1350.00 + 3000.00 = 4350.00 / 12 = 362.50
    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("362.50")


def test_provision_acumulada_coincide_con_lo_pagado(client, db):
    headers = _preparar_empresa(db, client)
    # fecha_inicio bien antes del cuatrimestre, pero dentro de 2025:
    # las tasas de CSS/ISR solo están sembradas desde 2025-01-01
    # (migraciones 0003/0010), así que las planillas regulares de este
    # test no pueden caer en 2024.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    # Cubre el cuatrimestre abr-ago 2025 (16-abr a 15-ago) con planillas
    # regulares: quincenal (16-30 abr) + 3 mensuales (may/jun/jul) +
    # quincenal (1-15 ago) -- única forma de calzar exactamente los
    # bordes del cuatrimestre con los tipos de período que Fase 6/7
    # aceptan.
    _generar_planilla(client, headers, "quincenal", datetime.date(2025, 4, 16), datetime.date(2025, 4, 30))
    provisiones = _provisiones(client, headers, contrato_id)
    prov = next(p for p in provisiones if p["cuatrimestre"] == "abr-ago" and p["anio"] == 2025)
    # Solo 16-abr a 30-abr = 15 días comerciales -> 15*30.00=450.00/12=37.50
    assert decimal.Decimal(str(prov["monto_acumulado"])) == decimal.Decimal("37.50")
    assert prov["pagado"] is False

    _generar_planilla(client, headers, "mensual", datetime.date(2025, 5, 1), datetime.date(2025, 5, 31))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 7, 1), datetime.date(2025, 7, 31))
    _generar_planilla(client, headers, "quincenal", datetime.date(2025, 8, 1), datetime.date(2025, 8, 15))

    provisiones = _provisiones(client, headers, contrato_id)
    prov = next(p for p in provisiones if p["cuatrimestre"] == "abr-ago" and p["anio"] == 2025)
    # Cuatrimestre completo -> 300.00 (ver test de año completo)
    monto_provisionado = decimal.Decimal(str(prov["monto_acumulado"]))
    assert monto_provisionado == decimal.Decimal("300.00")
    assert prov["pagado"] is False

    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    # Lo pagado coincide exactamente con lo que ya estaba provisionado
    # antes de generar el pago.
    assert decimal.Decimal(str(mov["salario_bruto"])) == monto_provisionado

    provisiones = _provisiones(client, headers, contrato_id)
    prov = next(p for p in provisiones if p["cuatrimestre"] == "abr-ago" and p["anio"] == 2025)
    assert prov["pagado"] is True
    assert prov["fecha_pago_real"] == "2025-08-15"
    assert prov["movimiento_planilla_id"] == mov["id"]


def test_ausencia_injustificada_reduce_el_decimo(client, db):
    headers = _preparar_empresa(db, client)
    # Mismo cuatrimestre completo del primer test (120 días comerciales
    # a 900/mes -> 3600.00/12=300.00 sin novedades). Ausencia
    # injustificada de 10 días (1 al 10 de mayo, sin cruzar fin de mes)
    # -- "sin goce de salario" (confirmado por el usuario 2026-08-20,
    # ver ausencias_service._SIN_GOCE_SALARIO): 120-10=110 días
    # comerciales -> 110*30.00=3300.00/12=275.00.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 1, 1))
    _registrar_ausencia(
        client, headers, contrato_id, "injustificada", datetime.date(2025, 5, 1), datetime.date(2025, 5, 10)
    )

    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("275.00")


def test_ausencia_con_goce_de_salario_no_reduce_el_decimo(client, db):
    headers = _preparar_empresa(db, client)
    # Mismo cuatrimestre y mismo rango de fechas que el test anterior,
    # pero enfermedad_dentro_fondo tiene salario completo por texto
    # expreso del Art. 200 CT -- no debe reducir el décimo. Sigue en
    # 300.00, igual que sin ninguna ausencia registrada.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 1, 1))
    _registrar_ausencia(
        client,
        headers,
        contrato_id,
        "enfermedad_dentro_fondo",
        datetime.date(2025, 5, 1),
        datetime.date(2025, 5, 10),
    )

    resp = _generar_pago_decimo(client, headers, "abr-ago", 2025, datetime.date(2025, 8, 15))
    assert resp.status_code == 201, resp.text
    mov = _movimiento_de(
        client.get(f"/planillas/{resp.json()['id']}/movimientos", headers=headers).json(),
        contrato_id,
    )
    assert decimal.Decimal(str(mov["salario_bruto"])) == decimal.Decimal("300.00")


def test_generar_pago_decimo_duplicado_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, datetime.date(2024, 1, 1))

    primera = _generar_pago_decimo(client, headers, "ago-dic", 2025, datetime.date(2025, 12, 15))
    assert primera.status_code == 201, primera.text

    segunda = _generar_pago_decimo(client, headers, "ago-dic", 2025, datetime.date(2025, 12, 15))
    assert segunda.status_code == 409, segunda.text

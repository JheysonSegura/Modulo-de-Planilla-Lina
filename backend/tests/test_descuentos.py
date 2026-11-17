import calendar
import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Préstamos y descuentos recurrentes (Art. 161 CT), decisiones del usuario
# 2026-11-17 -- ver PLAN-descuentos-prestamos.md. Salario 900.00/mes: una
# quincena da bruto 450.00, CSS 43.88, SE 5.62, ISR 4.38 -> neto de ley
# 396.12 (mismo caso base que test_vacaciones / Fase 17).
SALARIO = "900.00"
NETO_QUINCENA = decimal.Decimal("396.12")


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _d(valor) -> decimal.Decimal:
    return decimal.Decimal(str(valor))


def _preparar_empresa(db, client) -> dict:
    # Mínimo mensual 240.00 -> 120.00 por quincena (tope de embargo).
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("240.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _crear_contrato(client, headers, fecha_inicio=datetime.date(2025, 1, 1)):
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": f"Empleado {_sufijo()}"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        f"/empleados/{resp.json()['id']}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Prueba descuentos",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": SALARIO,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _registrar_descuento(client, headers, contrato_id, **datos):
    body = {"acreedor": "Banco General", "frecuencia": "quincenal", **datos}
    for clave in ("fecha_inicio",):
        if isinstance(body.get(clave), datetime.date):
            body[clave] = body[clave].isoformat()
    for clave in ("monto_total", "cuota"):
        if clave in body:
            body[clave] = str(body[clave])
    return client.post(f"/contratos/{contrato_id}/descuentos", json=body, headers=headers)


def _descuentos(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/descuentos", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _generar_planilla(client, headers, tipo, inicio, fin):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": tipo,
            "periodo_inicio": inicio.isoformat(),
            "periodo_fin": fin.isoformat(),
            "fecha_pago": fin.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _movimiento(client, headers, planilla_id, contrato_id):
    resp = client.get(f"/planillas/{planilla_id}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    return next(m for m in resp.json() if m["contrato_id"] == contrato_id)


def _quincena(client, headers, anio, mes, mitad):
    if mitad == 1:
        inicio, fin = datetime.date(anio, mes, 1), datetime.date(anio, mes, 15)
    else:
        inicio = datetime.date(anio, mes, 16)
        fin = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])
    return _generar_planilla(client, headers, "quincenal", inicio, fin)


def _neto_de_ley(mov) -> decimal.Decimal:
    return (
        _d(mov["salario_bruto"]) - _d(mov["css_empleado"])
        - _d(mov["seguro_educativo_empleado"]) - _d(mov["isr_retenido"])
    )


def _conceptos(mov, codigo):
    return [c for c in mov["conceptos_variables"] if c["codigo"] == codigo]


def test_simular_calcula_cuotas_y_la_ultima_absorbe_los_centavos(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    resp = client.post(
        f"/contratos/{contrato_id}/descuentos/simular",
        json={
            "monto_total": "1000.00",
            "plazo_meses": 3,
            "frecuencia": "quincenal",
            "fecha_inicio": "2026-01-01",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    sim = resp.json()
    # 1000 / 6 = 166.666... -> 166.66 × 5 = 833.30; última 166.70.
    assert sim["numero_cuotas"] == 6
    assert _d(sim["cuota"]) == _d("166.66")
    assert _d(sim["ultima_cuota"]) == _d("166.70")
    assert sim["fecha_primera_cuota"] == "2026-01-15"
    assert sim["fecha_ultima_cuota"] == "2026-03-31"


def test_prestamo_quincenal_se_cobra_del_neto_y_baja_el_saldo(client, db):
    """B/.1,200 a 6 meses quincenal = 12 cuotas de 100.00. La cuota sale
    del neto, no toca la base de CSS/SE/ISR."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    resp = _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario", referencia="PR-1",
        monto_total="1200.00", plazo_meses=6, fecha_inicio=datetime.date(2026, 1, 1),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["numero_cuotas"] == 12
    assert _d(resp.json()["cuota"]) == _d("100.00")

    planilla = _quincena(client, headers, 2026, 1, 1)
    mov = _movimiento(client, headers, planilla["id"], contrato_id)
    assert _neto_de_ley(mov) == NETO_QUINCENA
    assert _d(mov["otras_deducciones"]) == _d("100.00")
    assert _d(mov["salario_neto"]) == NETO_QUINCENA - _d("100.00")
    (concepto,) = _conceptos(mov, "prestamo_bancario")
    assert concepto["tipo"] == "deduccion"
    assert "Banco General" in concepto["descripcion"]
    assert "cuota 1 de 12" in concepto["descripcion"]
    # 100.00 > 20% de 396.12 (79.22): solo avisa (Art. 161.11).
    assert any("161.11" in a for a in mov["advertencias"])

    (descuento,) = _descuentos(client, headers, contrato_id)
    assert _d(descuento["saldo"]) == _d("1100.00")
    assert descuento["cuotas_cobradas"] == 1
    assert descuento["estado_actual"] == "activo"


def test_frecuencia_mensual_se_cobra_una_vez_al_mes_en_la_segunda_quincena(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_empresa", acreedor="Empresa",
        monto_total="300.00", plazo_meses=6, frecuencia="mensual",
        fecha_inicio=datetime.date(2026, 2, 1),
    )
    primera = _movimiento(client, headers, _quincena(client, headers, 2026, 2, 1)["id"], contrato_id)
    assert _conceptos(primera, "prestamo_empresa") == []
    segunda = _movimiento(client, headers, _quincena(client, headers, 2026, 2, 2)["id"], contrato_id)
    (concepto,) = _conceptos(segunda, "prestamo_empresa")
    assert _d(concepto["monto"]) == _d("50.00")


def test_ultima_cuota_cuadra_el_total_y_el_prestamo_queda_pagado(client, db):
    """1,000 a 3 meses mensual: 333.33 + 333.33 + 333.34 = 1,000.00 exacto."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_empresa", acreedor="Empresa",
        monto_total="1000.00", plazo_meses=3, frecuencia="mensual",
        fecha_inicio=datetime.date(2026, 1, 1),
    )
    montos = []
    for mes in (1, 2, 3, 4):
        fin = datetime.date(2026, mes, calendar.monthrange(2026, mes)[1])
        planilla = _generar_planilla(client, headers, "mensual", datetime.date(2026, mes, 1), fin)
        mov = _movimiento(client, headers, planilla["id"], contrato_id)
        montos.append(sum((_d(c["monto"]) for c in _conceptos(mov, "prestamo_empresa")), _d("0")))
    assert montos == [_d("333.33"), _d("333.33"), _d("333.34"), _d("0")]
    (descuento,) = _descuentos(client, headers, contrato_id)
    assert _d(descuento["saldo"]) == _d("0.00")
    assert descuento["estado_actual"] == "pagado"


def test_anular_la_planilla_devuelve_la_cuota_al_saldo(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario",
        monto_total="1200.00", plazo_meses=6, fecha_inicio=datetime.date(2026, 1, 1),
    )
    planilla = _quincena(client, headers, 2026, 1, 1)
    assert _d(_descuentos(client, headers, contrato_id)[0]["saldo"]) == _d("1100.00")

    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text
    assert _d(_descuentos(client, headers, contrato_id)[0]["saldo"]) == _d("1200.00")

    # Regenerada, vuelve a cobrar la misma cuota 1.
    mov = _movimiento(client, headers, _quincena(client, headers, 2026, 1, 1)["id"], contrato_id)
    assert "cuota 1 de 12" in _conceptos(mov, "prestamo_bancario")[0]["descripcion"]


def test_si_el_neto_no_alcanza_cobra_hasta_cero_y_el_resto_queda_en_saldo(client, db):
    """Cuota 500 contra un neto de 396.12: se cobran 396.12, el neto queda
    en 0 (nunca negativo) y 103.88 siguen en el saldo."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_empresa", acreedor="Empresa",
        monto_total="1000.00", plazo_meses=1, fecha_inicio=datetime.date(2026, 1, 1),
    )
    mov = _movimiento(client, headers, _quincena(client, headers, 2026, 1, 1)["id"], contrato_id)
    assert _d(mov["salario_neto"]) == _d("0.00")
    assert _d(mov["otras_deducciones"]) == NETO_QUINCENA
    assert any("neto no alcanzaba" in a for a in mov["advertencias"])
    assert _d(_descuentos(client, headers, contrato_id)[0]["saldo"]) == _d("1000.00") - NETO_QUINCENA


def test_vacaciones_cobran_las_cuotas_del_descanso_y_la_quincena_no_las_repite(client, db):
    """Descanso del 1 al 30-mar (30 días): cubre los cobros del 15 y del
    31-mar (base comercial). Las quincenas de marzo salen en 0 y no cobran
    nada; la 1ª de abril cobra la cuota del 15-abr."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario",
        monto_total="1200.00", plazo_meses=6, fecha_inicio=datetime.date(2026, 3, 1),
    )
    resp = client.post(
        f"/contratos/{contrato_id}/vacaciones-tomadas",
        json={"fecha": "2026-03-01", "dias": "30"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = client.get(f"/contratos/{contrato_id}/vacaciones-tomadas", headers=headers)
    planilla_vac = next(e for e in resp.json() if not e["anulada"])["planilla_id"]
    mov_vac = _movimiento(client, headers, planilla_vac, contrato_id)
    assert _d(mov_vac["otras_deducciones"]) == _d("200.00")
    assert _d(mov_vac["salario_neto"]) == _neto_de_ley(mov_vac) - _d("200.00")
    assert "cuotas 1 y 2 de 12" in _conceptos(mov_vac, "prestamo_bancario")[0]["descripcion"]
    evento_id = next(e for e in resp.json() if not e["anulada"])["id"]
    for formato in ("pdf", "excel"):
        recibo = client.get(
            f"/contratos/{contrato_id}/vacaciones-tomadas/{evento_id}/recibo",
            params={"formato": formato}, headers=headers,
        )
        assert recibo.status_code == 200, recibo.text

    for mitad in (1, 2):
        mov = _movimiento(client, headers, _quincena(client, headers, 2026, 3, mitad)["id"], contrato_id)
        assert _conceptos(mov, "prestamo_bancario") == []
        assert _d(mov["salario_neto"]) >= _d("0")

    mov_abril = _movimiento(client, headers, _quincena(client, headers, 2026, 4, 1)["id"], contrato_id)
    assert "cuota 3 de 12" in _conceptos(mov_abril, "prestamo_bancario")[0]["descripcion"]
    assert _d(_descuentos(client, headers, contrato_id)[0]["saldo"]) == _d("900.00")


def test_embargo_avisa_si_pasa_el_15_por_ciento_del_excedente_sobre_el_minimo(client, db):
    """Neto 396.12 − mínimo de la quincena 120.00 = 276.12; 15% = 41.42.
    Una cuota de embargo de 50.00 avisa; la pensión alimenticia no cuenta
    para el 50% total."""
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="embargo", acreedor="Juzgado 1",
        cuota="50.00", fecha_inicio=datetime.date(2026, 1, 1),
    )
    _registrar_descuento(
        client, headers, contrato_id, tipo="pension_alimenticia", acreedor="Juzgado de Niñez",
        cuota="250.00", fecha_inicio=datetime.date(2026, 1, 1),
    )
    mov = _movimiento(client, headers, _quincena(client, headers, 2026, 1, 1)["id"], contrato_id)
    assert _d(mov["otras_deducciones"]) == _d("300.00")
    assert any("Embargo" in a and "B/.41.42" in a for a in mov["advertencias"])
    # Total sin pensión = 50.00 < 50% de 396.12: no hay aviso de tope total.
    assert not any("161.13" in a for a in mov["advertencias"])
    # Sin monto total: no tienen saldo, siguen hasta que se cierren.
    assert all(d["saldo"] is None for d in _descuentos(client, headers, contrato_id))


def test_cerrar_detiene_el_cobro_y_borrar_solo_sin_cuotas(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    resp = _registrar_descuento(
        client, headers, contrato_id, tipo="cooperativa", acreedor="Coop. Ahorro",
        cuota="20.00", fecha_inicio=datetime.date(2026, 1, 1),
    )
    cooperativa_id = resp.json()["id"]
    resp = _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario",
        monto_total="600.00", plazo_meses=6, fecha_inicio=datetime.date(2026, 6, 1),
    )
    sin_cuotas_id = resp.json()["id"]

    _quincena(client, headers, 2026, 1, 1)
    resp = client.delete(f"/descuentos/{cooperativa_id}", headers=headers)
    assert resp.status_code == 409, resp.text
    resp = client.delete(f"/descuentos/{sin_cuotas_id}", headers=headers)
    assert resp.status_code == 204, resp.text

    resp = client.post(
        f"/descuentos/{cooperativa_id}/cerrar", json={"motivo": "Carta de retiro"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado_actual"] == "cerrado"
    mov = _movimiento(client, headers, _quincena(client, headers, 2026, 1, 2)["id"], contrato_id)
    assert _conceptos(mov, "cooperativa") == []

    resp = client.get(f"/descuentos/{cooperativa_id}/cuotas", headers=headers)
    assert resp.status_code == 200, resp.text
    assert [c["origen"] for c in resp.json()] == ["quincenal"]


def test_prestamo_sin_monto_ni_plazo_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    resp = _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario",
        cuota="100.00", fecha_inicio=datetime.date(2026, 1, 1),
    )
    assert resp.status_code == 422, resp.text


def test_reporte_por_acreedor(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo="prestamo_bancario",
        monto_total="1200.00", plazo_meses=6, fecha_inicio=datetime.date(2026, 1, 1),
    )
    planilla = _quincena(client, headers, 2026, 1, 1)
    resp = client.get(
        f"/planillas/{planilla['id']}/descuentos-acreedores", params={"formato": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    texto = resp.content.decode("utf-8-sig")
    assert "Banco General" in texto
    assert "Subtotal Banco General" in texto
    assert "TOTAL" in texto


# --- Liquidación (Art. 164 CT) -------------------------------------------


def _liquidar(client, headers, contrato_id, **extra):
    return client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={"motivo": "renuncia_voluntaria", "fecha_terminacion": "2026-02-15", **extra},
        headers=headers,
    )


def _contrato_con_prestamo(client, headers, tipo="prestamo_empresa"):
    """Préstamo de 600 a 6 meses mensual, enero ya cobrado (100) -> saldo 500."""
    contrato_id = _crear_contrato(client, headers)
    _registrar_descuento(
        client, headers, contrato_id, tipo=tipo, acreedor="Empresa" if tipo == "prestamo_empresa"
        else "Banco General", monto_total="600.00", plazo_meses=6, frecuencia="mensual",
        fecha_inicio=datetime.date(2026, 1, 1),
    )
    return contrato_id


def test_liquidacion_descuenta_el_saldo_del_prestamo_de_la_empresa(client, db):
    headers = _preparar_empresa(db, client)
    sin_prestamo = _crear_contrato(client, headers)
    con_casilla = _contrato_con_prestamo(client, headers)
    manual = _contrato_con_prestamo(client, headers)
    banco = _contrato_con_prestamo(client, headers, tipo="prestamo_bancario")
    _generar_planilla(client, headers, "mensual", datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))

    base = _liquidar(client, headers, sin_prestamo)
    assert base.status_code == 201, base.text
    total_base = _d(base.json()["monto_total"])
    assert _d(base.json()["descuento_prestamo_empresa"]) == _d("0")

    # Casilla marcada (por defecto): descuenta el saldo completo, 500.00.
    resp = _liquidar(client, headers, con_casilla)
    assert resp.status_code == 201, resp.text
    liq = resp.json()
    assert _d(liq["descuento_prestamo_empresa"]) == _d("500.00")
    assert liq["descuento_prestamo_manual"] is False
    assert _d(liq["monto_total"]) == total_base - _d("500.00")
    assert _descuentos(client, headers, con_casilla)[0]["estado_actual"] == "pagado"

    # Anular la liquidación devuelve el saldo.
    resp = client.post(f"/liquidaciones/{liq['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text
    assert _d(_descuentos(client, headers, con_casilla)[0]["saldo"]) == _d("500.00")

    # Sin casilla: monto manual + observación obligatoria.
    resp = _liquidar(client, headers, manual, descontar_prestamo_empresa=False,
                     monto_prestamo_empresa="200.00")
    assert resp.status_code == 422, resp.text
    resp = _liquidar(client, headers, manual, descontar_prestamo_empresa=False,
                     monto_prestamo_empresa="200.00",
                     observacion_prestamo_empresa="Acuerdo con gerencia")
    assert resp.status_code == 201, resp.text
    liq = resp.json()
    assert _d(liq["descuento_prestamo_empresa"]) == _d("200.00")
    assert liq["descuento_prestamo_manual"] is True
    assert liq["observacion_descuento_prestamo"] == "Acuerdo con gerencia"
    assert _d(liq["monto_total"]) == total_base - _d("200.00")
    assert _d(_descuentos(client, headers, manual)[0]["saldo"]) == _d("300.00")
    for formato in ("pdf", "excel"):
        recibo = client.get(
            f"/liquidaciones/{liq['id']}/recibo", params={"formato": formato}, headers=headers
        )
        assert recibo.status_code == 200, recibo.text

    # Préstamo con un banco: nunca se descuenta de la liquidación.
    resp = _liquidar(client, headers, banco)
    assert resp.status_code == 201, resp.text
    assert _d(resp.json()["monto_total"]) == total_base
    (descuento,) = _descuentos(client, headers, banco)
    assert _d(descuento["saldo"]) == _d("500.00")
    assert descuento["estado_actual"] == "terminado"

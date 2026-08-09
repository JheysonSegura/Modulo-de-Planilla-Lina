import base64
import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Mismo salario que test_decimo.py/test_vacaciones.py: 900.00/mes ->
# salario_diario=30.00 exacto, cuentas a mano simples. Ver
# FASE11-plan-ausencias.txt para el catálogo de tipos y su efecto.
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
            "cargo": "Prueba ausencias",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": str(salario_base),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


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


def _provision_vacaciones_abierta(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/provisiones-vacaciones", headers=headers)
    assert resp.status_code == 200, resp.text
    return next(p for p in resp.json() if p["estado"] == "abierto")


def test_ausencia_embarazo_no_reduce_vacaciones_sin_importar_duracion(client, db):
    headers = _preparar_empresa(db, client)
    # 2024-12-15 a 2025-04-30 = 137 días -> 12.45 días / 373.64 sin
    # ausencias (ver test_vacaciones.py). El embarazo (Art. 199.4 CT)
    # nunca se descuenta, aunque dure más de 15 días.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _registrar_ausencia(
        client, headers, contrato_id, "embarazo", datetime.date(2025, 2, 1), datetime.date(2025, 3, 2)
    )

    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
    prov = _provision_vacaciones_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.45")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("373.64")


def test_ausencia_enfermedad_excede_fondo_solo_descuenta_el_exceso_sobre_15_dias(client, db):
    headers = _preparar_empresa(db, client)
    # Mismo baseline de 137 días. Ausencia de 20 días: los primeros 15
    # quedan protegidos (Art. 208 CT), se descuentan solo 5.
    # 137-5=132 días -> 132/11=12.00 días exacto -> 12*30.00=360.00.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _registrar_ausencia(
        client,
        headers,
        contrato_id,
        "enfermedad_excede_fondo",
        datetime.date(2025, 1, 1),
        datetime.date(2025, 1, 20),
    )

    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
    prov = _provision_vacaciones_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.00")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("360.00")


def test_ausencia_enfermedad_excede_fondo_bajo_el_umbral_no_descuenta(client, db):
    headers = _preparar_empresa(db, client)
    # Ausencia de solo 10 días (bajo el umbral de 15): no descuenta
    # nada, el baseline de 137 días / 12.45 / 373.64 no cambia.
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2024, 12, 15))
    _registrar_ausencia(
        client,
        headers,
        contrato_id,
        "enfermedad_excede_fondo",
        datetime.date(2025, 1, 1),
        datetime.date(2025, 1, 10),
    )

    _generar_planilla(client, headers, "mensual", datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
    prov = _provision_vacaciones_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("12.45")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("373.64")


def test_recalculo_completo_con_ausencia_capturada_entre_planillas_sucesivas(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _registrar_ausencia(
        client, headers, contrato_id, "injustificada", datetime.date(2025, 1, 1), datetime.date(2025, 1, 11)
    )

    # Enero (31 días) menos 11 días de ausencia = 20 días ->
    # 20/11=1.818181... -> 1.82 días; 20/11*30.00=54.5454... -> 54.55.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    prov = _provision_vacaciones_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("1.82")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("54.55")

    # Enero+Febrero (59 días) menos los mismos 11 días de ausencia (ya
    # cubiertos en enero, no se duplican) = 48 días ->
    # 48/11=4.363636... -> 4.36 días; 48/11*30.00=130.9090... -> 130.91.
    # Confirma recálculo completo (no incremental) incluyendo la
    # ausencia de forma consistente.
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 2, 1), datetime.date(2025, 2, 28))
    prov = _provision_vacaciones_abierta(client, headers, contrato_id)
    assert decimal.Decimal(str(prov["dias_acumulados"])) == decimal.Decimal("4.36")
    assert decimal.Decimal(str(prov["monto_provisionado"])) == decimal.Decimal("130.91")


def test_tipo_de_ausencia_invalido_es_rechazado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = client.post(
        f"/contratos/{contrato_id}/ausencias",
        json={"tipo": "vacaciones_pagadas", "fecha_desde": "2025-01-01", "fecha_hasta": "2025-01-05"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def test_fecha_hasta_anterior_a_fecha_desde_es_rechazada(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))

    resp = client.post(
        f"/contratos/{contrato_id}/ausencias",
        json={"tipo": "injustificada", "fecha_desde": "2025-01-10", "fecha_hasta": "2025-01-05"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def _png_1x1() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def test_documento_ausencia_subir_y_obtener(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    ausencia = _registrar_ausencia(
        client, headers, contrato_id, "injustificada", datetime.date(2025, 1, 5), datetime.date(2025, 1, 6)
    )
    assert ausencia["tiene_documento_constancia"] is False
    png = _png_1x1()

    resp = client.put(
        f"/ausencias/{ausencia['id']}/documento",
        files={"archivo": ("constancia.png", png, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tiene_documento_constancia"] is True
    assert resp.json()["documento_constancia_nombre_archivo"] == "constancia.png"

    resp = client.get(f"/ausencias/{ausencia['id']}/documento", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png


def test_documento_ausencia_rechaza_formato_no_soportado(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    ausencia = _registrar_ausencia(
        client, headers, contrato_id, "injustificada", datetime.date(2025, 1, 5), datetime.date(2025, 1, 6)
    )

    resp = client.put(
        f"/ausencias/{ausencia['id']}/documento",
        files={"archivo": ("constancia.txt", b"contenido", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422

import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

SALARIO = "900.00"


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> dict:
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _crear_empleado_con_contrato(client, headers, fecha_inicio=datetime.date(2025, 1, 1)):
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
            "cargo": "Prueba horas extra aplicadas",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": SALARIO,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return empleado_id, resp.json()["id"]


def _registrar_hora_extra(
    client, headers, contrato_id, fecha=datetime.date(2025, 1, 10), horas="1.0"
):
    resp = client.post(
        f"/contratos/{contrato_id}/horas-extra",
        json={"fecha": fecha.isoformat(), "tipo_hora": "diurna", "tipo_dia": "ordinario", "horas": horas},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _generar_planilla(client, headers, periodo_inicio, periodo_fin):
    return client.post(
        "/planillas/generar",
        json={
            "tipo": "mensual",
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )


def test_borrar_hora_extra_antes_de_cualquier_planilla_funciona_igual_que_antes(client, db):
    headers = _preparar_empresa(db, client)
    _, contrato_id = _crear_empleado_con_contrato(client, headers)
    registro_id = _registrar_hora_extra(client, headers, contrato_id)

    resp = client.delete(f"/contratos/{contrato_id}/horas-extra/{registro_id}", headers=headers)
    assert resp.status_code == 204, resp.text


def test_no_se_puede_borrar_una_hora_extra_ya_aplicada_a_una_planilla(client, db):
    headers = _preparar_empresa(db, client)
    _, contrato_id = _crear_empleado_con_contrato(client, headers)
    registro_id = _registrar_hora_extra(client, headers, contrato_id)

    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()

    resp = client.get(f"/contratos/{contrato_id}/horas-extra", headers=headers)
    assert resp.status_code == 200, resp.text
    registro = next(r for r in resp.json() if r["id"] == registro_id)
    assert registro["aplicado"] is True

    resp = client.delete(f"/contratos/{contrato_id}/horas-extra/{registro_id}", headers=headers)
    assert resp.status_code == 409, resp.text

    # Anular la planilla libera el registro...
    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/contratos/{contrato_id}/horas-extra", headers=headers)
    registro = next(r for r in resp.json() if r["id"] == registro_id)
    assert registro["aplicado"] is False

    # ...y ahora sí se puede borrar.
    resp = client.delete(f"/contratos/{contrato_id}/horas-extra/{registro_id}", headers=headers)
    assert resp.status_code == 204, resp.text


def test_anular_libera_hora_extra_para_que_la_planilla_de_reemplazo_la_recoja(client, db):
    headers = _preparar_empresa(db, client)
    _, contrato_id = _crear_empleado_con_contrato(client, headers)
    _registrar_hora_extra(client, headers, contrato_id)

    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    resp = client.get(f"/planillas/{planilla['id']}/movimientos", headers=headers)
    monto_original = decimal.Decimal(resp.json()[0]["salario_bruto"])
    assert monto_original > decimal.Decimal(SALARIO)  # incluye la hora extra

    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text

    # Segundo intento sobre el mismo período ahora sí funciona y recoge
    # la misma hora extra (ya no está aplicada a la planilla anulada).
    resp = _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    assert resp.status_code == 201, resp.text
    nueva_planilla = resp.json()

    resp = client.get(f"/planillas/{nueva_planilla['id']}/movimientos", headers=headers)
    assert decimal.Decimal(resp.json()[0]["salario_bruto"]) == monto_original


def test_registrar_hora_extra_no_recalcula_una_ya_aplicada_de_la_misma_semana_iso(client, db):
    """La semana ISO lunes 27-ene a domingo 2-feb de 2025 cruza dos
    quincenas/planillas distintas. Se aplica primero la hora extra del
    sábado 1-feb (vía planilla de febrero) y luego se registra, tarde,
    una hora extra del lunes 27-ene (semana ISO anterior en fecha, pero
    capturada después). El registro de febrero ya está pagado -- su
    cálculo no debe cambiar aunque el nuevo registro consuma parte del
    tope semanal de 9h antes que él en el orden de la semana."""
    headers = _preparar_empresa(db, client)
    _, contrato_id = _crear_empleado_con_contrato(client, headers)

    registro_feb_id = _registrar_hora_extra(
        client, headers, contrato_id, fecha=datetime.date(2025, 2, 1), horas="2.0"
    )

    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 2, 1), datetime.date(2025, 2, 28)
    ).json()
    assert planilla is not None

    resp = client.get(f"/contratos/{contrato_id}/horas-extra", headers=headers)
    assert resp.status_code == 200, resp.text
    registro_antes = next(r for r in resp.json() if r["id"] == registro_feb_id)
    assert registro_antes["aplicado"] is True
    assert decimal.Decimal(registro_antes["horas_dentro_limite"]) == decimal.Decimal("2.0")
    assert decimal.Decimal(registro_antes["horas_exceso_limite"]) == decimal.Decimal("0")

    # Captura tardía de una hora extra del lunes de la misma semana ISO,
    # con suficientes horas para agotar el tope semanal antes de llegar
    # al registro de febrero ya pagado.
    _registrar_hora_extra(
        client, headers, contrato_id, fecha=datetime.date(2025, 1, 27), horas="8.0"
    )

    resp = client.get(f"/contratos/{contrato_id}/horas-extra", headers=headers)
    assert resp.status_code == 200, resp.text
    registro_despues = next(r for r in resp.json() if r["id"] == registro_feb_id)

    assert registro_despues["horas_dentro_limite"] == registro_antes["horas_dentro_limite"]
    assert registro_despues["horas_exceso_limite"] == registro_antes["horas_exceso_limite"]
    assert registro_despues["monto_dentro_limite"] == registro_antes["monto_dentro_limite"]
    assert registro_despues["monto_exceso_limite"] == registro_antes["monto_exceso_limite"]
    assert registro_despues["monto_calculado"] == registro_antes["monto_calculado"]

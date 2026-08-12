import base64
import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

SALARIO = "900.00"


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client, rol="admin") -> dict:
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, rol)
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
            "cargo": "Prueba auditoria",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": SALARIO,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return empleado_id, resp.json()["id"]


def _generar_planilla(client, headers, periodo_inicio, periodo_fin):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": "mensual",
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generar_liquidacion(client, headers, contrato_id, fecha_terminacion):
    resp = client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={"motivo": "mutuo_acuerdo", "fecha_terminacion": fecha_terminacion.isoformat()},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pdf_minimo() -> bytes:
    return base64.b64decode(
        "JVBERi0xLjENCiXi48/TDQoxIDAgb2JqDQo8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+"
        "Pg0KZW5kb2JqDQp4cmVmDQowIDENCjAwMDAwMDAwMDAgNjU1MzUgZg0KdHJhaWxlcg0KPDwv"
        "U2l6ZSAxPj4NCnN0YXJ0eHJlZg0KOQ0KJSVFT0Y="
    )


def _listar_auditoria(client, headers, **params):
    return client.get("/auditoria", params=params, headers=headers)


def test_cambio_de_salario_queda_auditado(client, db):
    headers = _preparar_empresa(db, client)
    empleado_id, contrato_id = _crear_empleado_con_contrato(client, headers)

    resp = client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "1000.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    resp = _listar_auditoria(client, headers, empleado_id=empleado_id)
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento["tabla_afectada"] == "contratos"
    assert evento["registro_id"] == contrato_id
    assert evento["accion"] == "cambio_salario"
    assert evento["empleado_id"] == empleado_id
    assert evento["datos_anteriores"]["salario_base"] == "900.00"
    assert evento["datos_nuevos"]["salario_base"] == "1000.00"
    assert evento["usuario_id"] is not None


def test_aprobar_planilla_queda_auditada_y_es_idempotente_al_rechazo(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    assert planilla["estado"] == "borrador"

    resp = client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "procesada"

    # Segunda aprobación sobre la misma planilla -> 409.
    resp2 = client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    assert resp2.status_code == 409, resp2.text

    resp = _listar_auditoria(client, headers, tabla_afectada="planillas", accion="aprobada")
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["registro_id"] == planilla["id"]
    assert eventos[0]["datos_anteriores"] == {"estado": "borrador"}
    assert eventos[0]["datos_nuevos"] == {"estado": "procesada"}
    assert eventos[0]["empleado_id"] is None  # evento de toda la empresa, no de un empleado


def test_calculo_y_pago_de_liquidacion_quedan_auditados(client, db):
    headers = _preparar_empresa(db, client)
    empleado_id, contrato_id = _crear_empleado_con_contrato(client, headers)
    _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    liquidacion = _generar_liquidacion(client, headers, contrato_id, datetime.date(2025, 2, 15))
    assert liquidacion["estado"] == "borrador"

    resp = client.post(f"/liquidaciones/{liquidacion['id']}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "aprobada"

    resp = client.post(
        f"/liquidaciones/{liquidacion['id']}/pagar",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "pagada"

    # Pagar de nuevo -> 409 (ya no está en 'aprobada').
    resp2 = client.post(
        f"/liquidaciones/{liquidacion['id']}/pagar",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp2.status_code == 409, resp2.text

    resp = _listar_auditoria(client, headers, empleado_id=empleado_id, tabla_afectada="liquidaciones")
    assert resp.status_code == 200, resp.text
    eventos = {e["accion"]: e for e in resp.json()}
    assert set(eventos.keys()) == {"calculada", "aprobada", "pagada"}
    assert eventos["calculada"]["datos_nuevos"]["monto_total"] is not None
    assert eventos["aprobada"]["datos_anteriores"] == {"estado": "borrador"}
    assert eventos["aprobada"]["datos_nuevos"] == {"estado": "aprobada"}
    assert eventos["pagada"]["datos_anteriores"] == {"estado": "aprobada"}
    assert eventos["pagada"]["datos_nuevos"] == {"estado": "pagada"}


def test_filtro_por_empleado_no_mezcla_eventos_de_otros_empleados(client, db):
    headers = _preparar_empresa(db, client)
    empleado_a, contrato_a = _crear_empleado_con_contrato(client, headers)
    empleado_b, contrato_b = _crear_empleado_con_contrato(client, headers)

    client.post(
        f"/contratos/{contrato_a}/salario",
        json={"salario_base": "1000.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers,
    )
    client.post(
        f"/contratos/{contrato_b}/salario",
        json={"salario_base": "1100.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers,
    )

    resp = _listar_auditoria(client, headers, empleado_id=empleado_a)
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["empleado_id"] == empleado_a
    assert eventos[0]["datos_nuevos"]["salario_base"] == "1000.00"


def test_endpoint_de_auditoria_rechaza_rol_no_admin(client, db):
    # No hace falta ningún dato de negocio real: solo se prueba que el
    # rol no-admin no puede leer el log de auditoría. 'consulta' además
    # no podría crear el empleado igual (ver test_permisos_escritura.py).
    headers = _preparar_empresa(db, client, rol="consulta")

    resp = _listar_auditoria(client, headers)
    assert resp.status_code == 403, resp.text


def test_auditoria_se_aisla_entre_empresas(client, db):
    headers_a = _preparar_empresa(db, client)
    _, contrato_a = _crear_empleado_con_contrato(client, headers_a)
    client.post(
        f"/contratos/{contrato_a}/salario",
        json={"salario_base": "1000.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers_a,
    )

    headers_b = _preparar_empresa(db, client)
    _, contrato_b = _crear_empleado_con_contrato(client, headers_b)
    client.post(
        f"/contratos/{contrato_b}/salario",
        json={"salario_base": "1200.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers_b,
    )

    resp = _listar_auditoria(client, headers_a, tabla_afectada="contratos")
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["datos_nuevos"]["salario_base"] == "1000.00"


# --- Fase 16 (extensión 2026-08-07): reporte de auditoría descargable ---


def test_exportar_auditoria_excel_y_csv(client, db):
    headers = _preparar_empresa(db, client)
    empleado_id, contrato_id = _crear_empleado_con_contrato(client, headers)
    client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "1000.00", "fecha_vigencia_desde": "2025-06-01"},
        headers=headers,
    )

    resp_excel = client.get("/auditoria/exportar?formato=excel", headers=headers)
    assert resp_excel.status_code == 200, resp_excel.text
    assert "spreadsheetml" in resp_excel.headers["content-type"]

    resp_csv = client.get("/auditoria/exportar?formato=csv", headers=headers)
    assert resp_csv.status_code == 200, resp_csv.text
    assert resp_csv.headers["content-type"].startswith("text/csv")
    assert b"cambio_salario" in resp_csv.content


def test_exportar_auditoria_rechaza_rol_no_admin(client, db):
    headers = _preparar_empresa(db, client, rol="consulta")

    resp = client.get("/auditoria/exportar?formato=excel", headers=headers)
    assert resp.status_code == 403, resp.text

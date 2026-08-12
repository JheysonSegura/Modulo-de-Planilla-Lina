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
            "cargo": "Prueba pagar",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": SALARIO,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return empleado_id, resp.json()["id"]


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


def _pdf_minimo() -> bytes:
    return base64.b64decode(
        "JVBERi0xLjENCiXi48/TDQoxIDAgb2JqDQo8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+"
        "Pg0KZW5kb2JqDQp4cmVmDQowIDENCjAwMDAwMDAwMDAgNjU1MzUgZg0KdHJhaWxlcg0KPDwv"
        "U2l6ZSAxPj4NCnN0YXJ0eHJlZg0KOQ0KJSVFT0Y="
    )


def test_no_se_puede_pagar_planilla_en_borrador(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    assert planilla["estado"] == "borrador"

    resp = client.post(
        f"/planillas/{planilla['id']}/pagar",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


def test_pagar_exige_archivo(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    resp = client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/planillas/{planilla['id']}/pagar", headers=headers)
    assert resp.status_code == 422, resp.text


def test_pagar_rechaza_formato_no_soportado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)

    resp = client.post(
        f"/planillas/{planilla['id']}/pagar",
        files={"archivo": ("constancia.txt", b"contenido", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def test_pagar_planilla_procesada_cambia_estado_guarda_constancia_y_queda_auditada(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    resp = client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "procesada"

    pdf = _pdf_minimo()
    resp = client.post(
        f"/planillas/{planilla['id']}/pagar",
        files={"archivo": ("constancia.pdf", pdf, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "pagada"
    assert body["tiene_constancia_pago"] is True
    assert body["documento_constancia_pago_nombre_archivo"] == "constancia.pdf"

    resp = client.get(f"/planillas/{planilla['id']}/constancia-pago", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == pdf

    resp = client.get(
        "/auditoria", params={"tabla_afectada": "planillas", "accion": "pagada"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["registro_id"] == planilla["id"]
    assert eventos[0]["datos_anteriores"] == {"estado": "procesada"}
    assert eventos[0]["datos_nuevos"] == {"estado": "pagada"}


def test_no_se_puede_pagar_dos_veces(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    resp = client.post(
        f"/planillas/{planilla['id']}/pagar",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/planillas/{planilla['id']}/pagar",
        files={"archivo": ("otra.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


def _pagar_planilla(client, headers, planilla_id, nombre_archivo="constancia.pdf"):
    resp = client.post(
        f"/planillas/{planilla_id}/pagar",
        files={"archivo": (nombre_archivo, _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_reemplazar_constancia_exitoso_no_cambia_estado_y_queda_auditado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    _pagar_planilla(client, headers, planilla["id"], "constancia-vieja.pdf")

    nueva_constancia = _pdf_minimo()
    resp = client.put(
        f"/planillas/{planilla['id']}/constancia-pago",
        files={"archivo": ("constancia-correcta.pdf", nueva_constancia, "application/pdf")},
        data={"motivo": "Se subió el comprobante de otra empresa por error"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "pagada"
    assert body["documento_constancia_pago_nombre_archivo"] == "constancia-correcta.pdf"

    resp = client.get(f"/planillas/{planilla['id']}/constancia-pago", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.content == nueva_constancia

    resp = client.get(
        "/auditoria",
        params={"tabla_afectada": "planillas", "accion": "constancia_repuesta"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["registro_id"] == planilla["id"]
    assert eventos[0]["datos_anteriores"] == {"archivo": "constancia-vieja.pdf"}
    assert eventos[0]["datos_nuevos"] == {
        "archivo": "constancia-correcta.pdf",
        "motivo": "Se subió el comprobante de otra empresa por error",
    }


def test_no_se_puede_reemplazar_constancia_si_no_esta_pagada(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)

    resp = client.put(
        f"/planillas/{planilla['id']}/constancia-pago",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        data={"motivo": "Motivo cualquiera"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


def test_reemplazar_constancia_requiere_rol_admin(client, db):
    headers = _preparar_empresa(db, client, rol="contador")
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    _pagar_planilla(client, headers, planilla["id"])

    resp = client.put(
        f"/planillas/{planilla['id']}/constancia-pago",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        data={"motivo": "Motivo cualquiera"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


def test_reemplazar_constancia_exige_motivo(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    _pagar_planilla(client, headers, planilla["id"])

    resp = client.put(
        f"/planillas/{planilla['id']}/constancia-pago",
        files={"archivo": ("constancia.pdf", _pdf_minimo(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def test_reemplazar_constancia_rechaza_formato_no_soportado(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    client.post(f"/planillas/{planilla['id']}/aprobar", headers=headers)
    _pagar_planilla(client, headers, planilla["id"])

    resp = client.put(
        f"/planillas/{planilla['id']}/constancia-pago",
        files={"archivo": ("constancia.txt", b"contenido", "text/plain")},
        data={"motivo": "Motivo cualquiera"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text

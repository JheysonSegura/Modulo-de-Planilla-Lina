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
            "cargo": "Prueba anular",
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


def test_anular_planilla_en_borrador_cambia_estado_y_queda_auditada(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    resp = _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    assert resp.status_code == 201, resp.text
    planilla = resp.json()
    assert planilla["estado"] == "borrador"

    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "anulada"

    resp = client.get("/auditoria", params={"tabla_afectada": "planillas", "accion": "anulada"}, headers=headers)
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["registro_id"] == planilla["id"]
    assert eventos[0]["datos_anteriores"] == {"estado": "borrador"}
    assert eventos[0]["datos_nuevos"] == {"estado": "anulada"}


def test_no_se_puede_anular_dos_veces_ni_una_planilla_ya_aprobada(client, db):
    headers = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers)
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()

    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text

    # Anular de nuevo -> 409.
    resp2 = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp2.status_code == 409, resp2.text

    # Una planilla procesada tampoco se puede anular.
    planilla2 = _generar_planilla(
        client, headers, datetime.date(2025, 2, 1), datetime.date(2025, 2, 28)
    ).json()
    resp = client.post(f"/planillas/{planilla2['id']}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/planillas/{planilla2['id']}/anular", headers=headers)
    assert resp.status_code == 409, resp.text


def test_anular_libera_conceptos_variables_para_la_planilla_de_reemplazo(client, db):
    headers = _preparar_empresa(db, client)
    _, contrato_id = _crear_empleado_con_contrato(client, headers)

    resp = client.post(
        f"/contratos/{contrato_id}/conceptos-variables-pendientes",
        json={
            "fecha": "2025-01-10",
            "tipo": "ingreso",
            "codigo": "bono_productividad",
            "monto": "150.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    concepto_id = resp.json()["id"]

    # Generar la planilla del período aplica el concepto pendiente.
    planilla = _generar_planilla(
        client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    ).json()
    resp = client.get(
        f"/contratos/{contrato_id}/conceptos-variables-pendientes", headers=headers
    )
    assert resp.status_code == 200, resp.text
    concepto = next(c for c in resp.json() if c["id"] == concepto_id)
    assert concepto["aplicado"] is True

    # Un segundo intento de generar la planilla del mismo período choca (ya existe una).
    resp = _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    assert resp.status_code == 409, resp.text

    # Se anula la planilla equivocada...
    resp = client.post(f"/planillas/{planilla['id']}/anular", headers=headers)
    assert resp.status_code == 200, resp.text

    # ...el concepto variable vuelve a estar disponible...
    resp = client.get(
        f"/contratos/{contrato_id}/conceptos-variables-pendientes", headers=headers
    )
    concepto = next(c for c in resp.json() if c["id"] == concepto_id)
    assert concepto["aplicado"] is False
    assert concepto["movimiento_planilla_id"] is None

    # ...y ahora sí se puede generar la planilla de reemplazo del mismo período, que lo recoge.
    resp = _generar_planilla(client, headers, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    assert resp.status_code == 201, resp.text
    nueva_planilla = resp.json()

    resp = client.get(f"/planillas/{nueva_planilla['id']}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimiento = resp.json()[0]
    assert movimiento["salario_bruto"] == "1050.00"  # 900 base + 150 del concepto recogido

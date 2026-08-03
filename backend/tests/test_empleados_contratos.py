import datetime
import decimal
import uuid

from tests.conftest import (
    crear_empresa,
    crear_salario_minimo,
    crear_usuario,
    login_y_seleccionar,
    vincular,
)


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa_con_usuario(db, client):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)
    return empresa, headers


def test_crear_empleado_y_contrato(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={
            "tipo_identificacion": "cedula",
            "identificacion": f"8-{_sufijo()}",
            "nombre_completo": "Ana Pérez",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado = resp.json()
    assert empleado["nombre_completo"] == "Ana Pérez"
    assert empleado["estado"] == "activo"

    resp = client.post(
        f"/empleados/{empleado['id']}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Analista",
            "fecha_inicio": "2024-01-01",
            "periodicidad_pago": "quincenal",
            "salario_base": "1200.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    contrato = resp.json()
    assert contrato["empleado_id"] == empleado["id"]
    assert contrato["cargo"] == "Analista"
    assert contrato["estado"] == "vigente"

    resp = client.get(f"/empleados/{empleado['id']}/contratos", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/contratos/{contrato['id']}/historial-salarial", headers=headers)
    assert resp.status_code == 200
    historial = resp.json()
    assert len(historial) == 1
    assert historial[0]["motivo"] == "ingreso"
    assert historial[0]["fecha_vigencia_hasta"] is None
    assert decimal.Decimal(str(historial[0]["salario_base"])) == decimal.Decimal("1200.00")


def test_actualizar_empleado_no_toca_identificacion_si_no_se_manda(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Carlos Ruiz"},
        headers=headers,
    )
    empleado = resp.json()

    resp = client.patch(
        f"/empleados/{empleado['id']}",
        json={"telefono": "6000-0000"},
        headers=headers,
    )
    assert resp.status_code == 200
    actualizado = resp.json()
    assert actualizado["telefono"] == "6000-0000"
    assert actualizado["identificacion"] == empleado["identificacion"]


def test_cambio_salario_no_borra_el_anterior_y_consulta_historica_es_correcta(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "María López"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Contadora",
            "fecha_inicio": "2024-01-01",
            "salario_base": "1000.00",
        },
        headers=headers,
    )
    contrato_id = resp.json()["id"]

    # Aumento de salario a partir de junio 2024.
    resp = client.post(
        f"/contratos/{contrato_id}/salario",
        json={
            "salario_base": "1500.00",
            "fecha_vigencia_desde": "2024-06-01",
            "motivo": "ajuste_anual",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    resp = client.get(f"/contratos/{contrato_id}/historial-salarial", headers=headers)
    historial = resp.json()
    assert len(historial) == 2

    original = next(h for h in historial if h["motivo"] == "ingreso")
    nuevo = next(h for h in historial if h["motivo"] == "ajuste_anual")

    # El registro original NO se borró ni se sobrescribió: sigue con su
    # salario, y ahora tiene fecha_vigencia_hasta cerrada justo antes de
    # que empiece el nuevo.
    assert decimal.Decimal(str(original["salario_base"])) == decimal.Decimal("1000.00")
    assert original["fecha_vigencia_hasta"] == "2024-05-31"
    assert decimal.Decimal(str(nuevo["salario_base"])) == decimal.Decimal("1500.00")
    assert nuevo["fecha_vigencia_hasta"] is None

    # "Salario del empleado en marzo" (antes del aumento) -> el histórico.
    resp = client.get(
        f"/contratos/{contrato_id}/salario-vigente",
        params={"fecha": "2024-03-15"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert decimal.Decimal(str(resp.json()["salario_base"])) == decimal.Decimal("1000.00")

    # Salario después del aumento -> el nuevo.
    resp = client.get(
        f"/contratos/{contrato_id}/salario-vigente",
        params={"fecha": "2024-07-01"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert decimal.Decimal(str(resp.json()["salario_base"])) == decimal.Decimal("1500.00")


def test_no_permite_retroceder_la_fecha_de_vigencia_del_salario(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado Test"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Auxiliar",
            "fecha_inicio": "2024-01-01",
            "salario_base": "800.00",
        },
        headers=headers,
    )
    contrato_id = resp.json()["id"]

    resp = client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "900.00", "fecha_vigencia_desde": "2023-12-01"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_rechaza_salario_por_debajo_del_minimo_vigente_en_la_fecha_del_contrato(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    # Salario mínimo vigente SOLO durante 2024.
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("800.00"),
        fecha_fin=datetime.date(2024, 12, 31),
    )

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado Bajo Mínimo"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]

    # Por debajo del mínimo vigente en esa fecha -> rechazado.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Auxiliar",
            "fecha_inicio": "2024-03-01",
            "salario_base": "700.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "mínimo" in resp.json()["detail"]

    # El mismo salario, pero en una fecha FUERA del rango vigente (2025,
    # sin dato sembrado) -> no hay nada contra qué validar, se acepta.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Auxiliar",
            "fecha_inicio": "2025-03-01",
            "salario_base": "700.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_rechaza_cambio_de_salario_por_debajo_del_minimo_vigente_en_esa_fecha(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("800.00"),
        fecha_fin=datetime.date(2024, 12, 31),
    )

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado Ajuste"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]

    # Contrato nace en 2023 (antes del mínimo sembrado), sin problema.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Auxiliar",
            "fecha_inicio": "2023-06-01",
            "salario_base": "700.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    contrato_id = resp.json()["id"]

    # El ajuste cae en 2024 (dentro del rango vigente) y queda por debajo.
    resp = client.post(
        f"/contratos/{contrato_id}/salario",
        json={"salario_base": "750.00", "fecha_vigencia_desde": "2024-02-01"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "mínimo" in resp.json()["detail"]


def test_no_ve_empleados_de_otra_empresa(client, db):
    empresa_a, headers_a = _preparar_empresa_con_usuario(db, client)
    empresa_b, headers_b = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado de B"},
        headers=headers_b,
    )
    empleado_b_id = resp.json()["id"]

    resp = client.get(f"/empleados/{empleado_b_id}", headers=headers_a)
    assert resp.status_code == 404

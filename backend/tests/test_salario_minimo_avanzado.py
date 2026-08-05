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


def _crear_empleado(client, headers) -> str:
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado de prueba"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_medio_tiempo_prorratea_el_minimo_en_vez_de_exigir_el_completo(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    crear_salario_minimo(
        db, datetime.date(2024, 1, 1), decimal.Decimal("600.00"), fecha_fin=datetime.date(2024, 12, 31)
    )
    empleado_id = _crear_empleado(client, headers)

    # Medio tiempo (24h/semana = mitad de las 48h de referencia): el
    # mínimo aplicable prorrateado es 300.00, no 600.00.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "definido",
            "cargo": "Auxiliar medio tiempo",
            "fecha_inicio": "2024-03-01",
            "jornada_horas_semana": "24",
            "salario_base": "320.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "definido",
            "cargo": "Auxiliar medio tiempo 2",
            "fecha_inicio": "2024-03-01",
            "jornada_horas_semana": "24",
            "salario_base": "250.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "prorrateado" in resp.json()["detail"]


def test_pasantia_exenta_de_validacion_de_salario_minimo(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    crear_salario_minimo(
        db, datetime.date(2024, 1, 1), decimal.Decimal("600.00"), fecha_fin=datetime.date(2024, 12, 31)
    )
    empleado_id = _crear_empleado(client, headers)

    # Sin exención, un estipendio de pasantía de $100 sería rechazado.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "definido",
            "cargo": "Pasante",
            "fecha_inicio": "2024-03-01",
            "salario_base": "100.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422

    # Con la exención explícita y su motivo, se acepta.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "definido",
            "cargo": "Pasante",
            "fecha_inicio": "2024-03-01",
            "salario_base": "100.00",
            "exento_salario_minimo": True,
            "motivo_exencion_salario_minimo": "Pasantía formal, convenio con universidad",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    contrato = resp.json()
    assert contrato["exento_salario_minimo"] is True

    # El ajuste de salario posterior en el mismo contrato también respeta
    # la exención (no se puede esquivar el flag cambiando el salario).
    resp = client.post(
        f"/contratos/{contrato['id']}/salario",
        json={"salario_base": "120.00", "fecha_vigencia_desde": "2024-06-01"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_exento_sin_motivo_es_rechazado_por_validacion(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    empleado_id = _crear_empleado(client, headers)

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "definido",
            "cargo": "Pasante",
            "fecha_inicio": "2024-03-01",
            "salario_base": "100.00",
            "exento_salario_minimo": True,
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_multi_region_elige_la_fila_segun_la_region_de_la_empresa(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    # PATCH /empresas/actual: la empresa se registra en "Región 2".
    resp = client.patch("/empresas/actual", json={"region": "Región 2"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["region"] == "Región 2"

    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("700.00"),
        region="Región 1",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=True,
    )
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("500.00"),
        region="Región 2",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=False,
    )

    empleado_id = _crear_empleado(client, headers)

    # $550 está por debajo del mínimo de Región 1 (700) pero por encima
    # del de Región 2 (500), que es donde está esta empresa -> se acepta.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario",
            "fecha_inicio": "2024-03-01",
            "salario_base": "550.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    # $450 está por debajo del mínimo de Región 2 (500) -> se rechaza.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario 2",
            "fecha_inicio": "2024-03-01",
            "salario_base": "450.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_multi_region_sin_region_configurada_es_ambiguo(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    # Esta empresa NO tiene region configurada (default None).

    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("700.00"),
        region="Región 1",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=True,
    )
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("500.00"),
        region="Región 2",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=False,
    )

    empleado_id = _crear_empleado(client, headers)

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario",
            "fecha_inicio": "2024-03-01",
            "salario_base": "550.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "región" in resp.json()["detail"].lower()


def test_solo_admin_puede_editar_empresa_actual(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "consulta")
    headers = login_y_seleccionar(client, usuario, empresa)

    resp = client.patch("/empresas/actual", json={"region": "Región 2"}, headers=headers)
    assert resp.status_code == 403


def test_tarifa_por_hora_se_convierte_a_mensual_30x8(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    # Decreto Ejecutivo N.13: tarifa por hora, no mensual. Equivalente
    # mensual = monto_hora * 8 * 30 = 3.00 * 8 * 30 = 720.00.
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        monto_hora=decimal.Decimal("3.00"),
        fecha_fin=datetime.date(2024, 12, 31),
    )
    empleado_id = _crear_empleado(client, headers)

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario",
            "fecha_inicio": "2024-03-01",
            "salario_base": "700.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "720.00" in resp.json()["detail"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario 2",
            "fecha_inicio": "2024-03-01",
            "salario_base": "720.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_tamano_empresa_elige_la_fila_correcta(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.patch(
        "/empresas/actual",
        json={"actividad_economica": "Comercio al por Menor", "tamano_empresa": "Gran Empresa"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("400.00"),
        actividad="Comercio al por Menor",
        tamano_empresa="Pequeña Empresa",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=True,
    )
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("900.00"),
        actividad="Comercio al por Menor",
        tamano_empresa="Gran Empresa",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=False,
    )

    empleado_id = _crear_empleado(client, headers)

    # $500 supera el mínimo de pequeña empresa (400) pero está por
    # debajo del de gran empresa (900), que es donde está esta empresa.
    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Cajero",
            "fecha_inicio": "2024-03-01",
            "salario_base": "500.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "900.00" in resp.json()["detail"]


def test_tamano_empresa_sin_configurar_es_ambiguo(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.patch(
        "/empresas/actual",
        json={"actividad_economica": "Comercio al por Menor"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    # tamano_empresa NO se configura (queda None).

    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("400.00"),
        actividad="Comercio al por Menor",
        tamano_empresa="Pequeña Empresa",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=True,
    )
    crear_salario_minimo(
        db,
        datetime.date(2024, 1, 1),
        decimal.Decimal("900.00"),
        actividad="Comercio al por Menor",
        tamano_empresa="Gran Empresa",
        fecha_fin=datetime.date(2024, 12, 31),
        limpiar=False,
    )

    empleado_id = _crear_empleado(client, headers)

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Cajero",
            "fecha_inicio": "2024-03-01",
            "salario_base": "500.00",
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "tamano_empresa" in resp.json()["detail"] or "tamaño" in resp.json()["detail"].lower()

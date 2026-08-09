import base64
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


def test_crear_empleado_con_datos_personales_nuevos(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={
            "identificacion": f"8-{_sufijo()}",
            "nombre_completo": "Rosa Jiménez",
            "fecha_nacimiento": "1990-05-20",
            "nacionalidad": "panameña",
            "sexo": "femenino",
            "codigo_pais": "+507",
            "telefono": "6123-4567",
            "padece_enfermedad": True,
            "detalle_enfermedad": "Asma",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado = resp.json()
    assert empleado["fecha_nacimiento"] == "1990-05-20"
    assert empleado["nacionalidad"] == "panameña"
    assert empleado["sexo"] == "femenino"
    assert empleado["codigo_pais"] == "+507"
    assert empleado["telefono"] == "6123-4567"
    assert empleado["padece_enfermedad"] is True
    assert empleado["detalle_enfermedad"] == "Asma"
    assert empleado["tiene_documento_identificacion"] is False
    assert empleado["tiene_documento_certificado_medico"] is False


def test_actualizar_empleado_campos_editables(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Julio Ábrego"},
        headers=headers,
    )
    empleado = resp.json()

    resp = client.patch(
        f"/empleados/{empleado['id']}",
        json={
            "telefono": "6789-0000",
            "codigo_pais": "+507",
            "direccion": "Vía España, PTY",
            "fecha_nacimiento": "1985-03-10",
            "sexo": "masculino",
            "nacionalidad": "panameña",
            "padece_enfermedad": True,
            "detalle_enfermedad": "Hipertensión",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    actualizado = resp.json()
    assert actualizado["telefono"] == "6789-0000"
    assert actualizado["codigo_pais"] == "+507"
    assert actualizado["direccion"] == "Vía España, PTY"
    assert actualizado["fecha_nacimiento"] == "1985-03-10"
    assert actualizado["sexo"] == "masculino"
    assert actualizado["nacionalidad"] == "panameña"
    assert actualizado["padece_enfermedad"] is True
    assert actualizado["detalle_enfermedad"] == "Hipertensión"


def test_actualizar_empleado_ignora_identificacion_nombre_y_email(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)

    resp = client.post(
        "/empleados",
        json={
            "identificacion": f"8-{_sufijo()}",
            "nombre_completo": "Nombre Original",
            "email_personal": "original@example.com",
        },
        headers=headers,
    )
    empleado = resp.json()

    resp = client.patch(
        f"/empleados/{empleado['id']}",
        json={
            "identificacion": "9-999-9999",
            "nombre_completo": "Nombre Cambiado",
            "email_personal": "cambiado@example.com",
            "direccion": "Nueva dirección",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    actualizado = resp.json()
    # Los 3 campos bloqueados no se movieron -- EmpleadoUpdate no los
    # declara, así que Pydantic los descarta antes de llegar al service.
    assert actualizado["identificacion"] == empleado["identificacion"]
    assert actualizado["nombre_completo"] == "Nombre Original"
    assert actualizado["email_personal"] == "original@example.com"
    assert actualizado["direccion"] == "Nueva dirección"


def _png_1x1() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def test_documento_identificacion_subir_y_obtener(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado con cédula"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]
    png = _png_1x1()

    resp = client.put(
        f"/empleados/{empleado_id}/documento-identificacion",
        files={"archivo": ("cedula.png", png, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tiene_documento_identificacion"] is True
    assert resp.json()["documento_identificacion_nombre_archivo"] == "cedula.png"

    resp = client.get(f"/empleados/{empleado_id}/documento-identificacion", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png


def test_documento_certificado_medico_subir_y_obtener(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado con certificado"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]
    png = _png_1x1()

    resp = client.put(
        f"/empleados/{empleado_id}/documento-certificado-medico",
        files={"archivo": ("certificado.png", png, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tiene_documento_certificado_medico"] is True

    resp = client.get(f"/empleados/{empleado_id}/documento-certificado-medico", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png


def test_documento_identificacion_rechaza_formato_no_soportado(client, db):
    empresa, headers = _preparar_empresa_con_usuario(db, client)
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado formato inválido"},
        headers=headers,
    )
    empleado_id = resp.json()["id"]

    resp = client.put(
        f"/empleados/{empleado_id}/documento-identificacion",
        files={"archivo": ("cedula.txt", b"contenido", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422

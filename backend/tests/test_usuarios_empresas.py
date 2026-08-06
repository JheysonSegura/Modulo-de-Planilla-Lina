import uuid

from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa_admin(db, client) -> dict:
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _listar(client, headers):
    return client.get("/empresas/actual/usuarios", headers=headers)


def _agregar(client, headers, **body):
    return client.post("/empresas/actual/usuarios", json=body, headers=headers)


def test_agregar_usuario_nuevo_crea_cuenta_y_vinculo(client, db):
    headers = _preparar_empresa_admin(db, client)
    email = f"nuevo-{_sufijo()}@example.com"

    resp = _agregar(
        client, headers, email=email, rol="contador", nombre_completo="Contador de Prueba",
        password="Secreta123!",
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == email
    assert data["nombre_completo"] == "Contador de Prueba"
    assert data["rol"] == "contador"
    assert data["activo"] is True

    resp = _listar(client, headers)
    assert resp.status_code == 200, resp.text
    assert any(u["email"] == email for u in resp.json())


def test_agregar_usuario_nuevo_sin_password_es_rechazado(client, db):
    headers = _preparar_empresa_admin(db, client)
    resp = _agregar(client, headers, email=f"sinpass-{_sufijo()}@example.com", rol="consulta")
    assert resp.status_code == 422, resp.text


def test_agregar_usuario_existente_solo_vincula(client, db):
    headers_a = _preparar_empresa_admin(db, client)

    # El mismo usuario ya tiene cuenta (creada al vincularse a otra empresa).
    otra_empresa_headers = _preparar_empresa_admin(db, client)
    email_compartido = f"compartido-{_sufijo()}@example.com"
    resp = _agregar(
        client, otra_empresa_headers, email=email_compartido, rol="admin",
        nombre_completo="Contador Multi-Empresa", password="Secreta123!",
    )
    assert resp.status_code == 201, resp.text

    # Se agrega a la primera empresa sin mandar password -- ya existe.
    resp = _agregar(client, headers_a, email=email_compartido, rol="consulta")
    assert resp.status_code == 201, resp.text
    assert resp.json()["rol"] == "consulta"


def test_agregar_usuario_ya_con_acceso_activo_es_rechazado(client, db):
    headers = _preparar_empresa_admin(db, client)
    email = f"duplicado-{_sufijo()}@example.com"
    primera = _agregar(
        client, headers, email=email, rol="contador", nombre_completo="X", password="Secreta123!",
    )
    assert primera.status_code == 201, primera.text

    segunda = _agregar(client, headers, email=email, rol="admin")
    assert segunda.status_code == 409, segunda.text


def test_cambiar_rol_y_desactivar_acceso(client, db):
    headers = _preparar_empresa_admin(db, client)
    email = f"cambio-{_sufijo()}@example.com"
    resp = _agregar(
        client, headers, email=email, rol="consulta", nombre_completo="X", password="Secreta123!",
    )
    usuario_empresa_id = resp.json()["id"]

    resp = client.patch(
        f"/empresas/actual/usuarios/{usuario_empresa_id}", json={"rol": "contador"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rol"] == "contador"

    resp = client.patch(
        f"/empresas/actual/usuarios/{usuario_empresa_id}", json={"activo": False}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False


def test_no_se_puede_modificar_el_propio_acceso(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"self-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)

    resp = _listar(client, headers)
    propio = next(u for u in resp.json() if u["email"] == usuario.email)

    resp = client.patch(
        f"/empresas/actual/usuarios/{propio['id']}", json={"activo": False}, headers=headers
    )
    assert resp.status_code == 422, resp.text


def test_endpoint_rechaza_rol_no_admin(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"consulta-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "consulta")
    headers = login_y_seleccionar(client, usuario, empresa)

    resp = _listar(client, headers)
    assert resp.status_code == 403, resp.text


def test_agregar_usuario_queda_auditado(client, db):
    headers = _preparar_empresa_admin(db, client)
    email = f"auditado-{_sufijo()}@example.com"
    resp = _agregar(
        client, headers, email=email, rol="contador", nombre_completo="X", password="Secreta123!",
    )
    assert resp.status_code == 201, resp.text

    resp = client.get(
        "/auditoria", params={"tabla_afectada": "usuarios_empresas", "accion": "acceso_otorgado"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["datos_nuevos"]["email"] == email

import uuid

from tests.conftest import crear_empleado, crear_empresa, crear_usuario, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def test_login_y_seleccion_de_empresa(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "Secreta123!"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.get("/auth/empresas", headers=headers)
    assert resp.status_code == 200
    empresas = resp.json()
    assert len(empresas) == 1
    assert empresas[0]["empresa_id"] == str(empresa.id)
    assert empresas[0]["rol"] == "admin"

    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa.id)}, headers=headers
    )
    assert resp.status_code == 200
    headers_con_empresa = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.get("/auth/me", headers=headers_con_empresa)
    assert resp.status_code == 200
    me = resp.json()
    assert me["empresa_activa_id"] == str(empresa.id)
    assert me["rol_activo"] == "admin"


def test_rechaza_password_incorrecto(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "incorrecta"})
    assert resp.status_code == 401


def test_no_puede_seleccionar_una_empresa_ajena(client, db):
    empresa_propia = crear_empresa(db, _sufijo())
    empresa_ajena = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa_propia, "admin")

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa_ajena.id)}, headers=headers
    )
    assert resp.status_code == 403


def test_requiere_seleccionar_empresa_antes_de_leer_datos(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Token válido, pero sin empresa activa: no debe poder leer nada.
    resp = client.get("/empleados", headers=headers)
    assert resp.status_code == 403


def test_no_ve_empleados_de_otra_empresa_ni_manipulando_empresa_id(client, db):
    empresa_a = crear_empresa(db, _sufijo())
    empresa_b = crear_empresa(db, _sufijo())

    empleado_a = crear_empleado(db, empresa_a, "Empleado A", f"ID-{_sufijo()}")
    empleado_b = crear_empleado(db, empresa_b, "Empleado B", f"ID-{_sufijo()}")

    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa_a, "admin")  # SOLO tiene acceso a la empresa A

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa_a.id)}, headers=headers
    )
    assert resp.status_code == 200
    headers_a = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Caso normal: solo ve empleados de su empresa activa.
    resp = client.get("/empleados", headers=headers_a)
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert str(empleado_a.id) in ids
    assert str(empleado_b.id) not in ids

    # Trampa 1: manda un query param empresa_id apuntando a la empresa B.
    # El endpoint no lo lee -> sigue viendo solo A (RLS, no el código).
    resp = client.get(f"/empleados?empresa_id={empresa_b.id}", headers=headers_a)
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert str(empleado_b.id) not in ids
    assert str(empleado_a.id) in ids

    # Trampa 2: nunca puede obtener un token con empresa_id=B, porque no
    # pertenece a esa empresa -> no hay forma de "seleccionarla" para atacar.
    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa_b.id)}, headers=headers
    )
    assert resp.status_code == 403


def test_refresh_rota_token_y_logout_revoca(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")

    resp = client.post("/auth/login", json={"email": usuario.email, "password": "Secreta123!"})
    tokens = resp.json()

    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    nuevos = resp.json()
    assert nuevos["refresh_token"] != tokens["refresh_token"]

    # El refresh token viejo fue rotado/revocado: no sirve una segunda vez.
    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401

    resp = client.post("/auth/logout", json={"refresh_token": nuevos["refresh_token"]})
    assert resp.status_code == 204

    resp = client.post("/auth/refresh", json={"refresh_token": nuevos["refresh_token"]})
    assert resp.status_code == 401

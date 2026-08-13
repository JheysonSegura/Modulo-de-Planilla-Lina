import uuid

from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def test_admin_sin_permiso_no_ve_mis_empresas(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    headers = login_y_seleccionar(client, admin, empresa)

    resp = client.get("/mis-empresas", headers=headers)
    assert resp.status_code == 403


def test_admin_delegado_ve_solo_sus_propias_empresas(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/empresas", json={"razon_social": "Propia", "ruc": f"RUC-{_sufijo()}"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    empresa_propia_id = resp.json()["id"]

    empresa_ajena = crear_empresa(db, _sufijo())  # no creada ni administrada por este admin

    resp = client.get("/mis-empresas", headers=headers)
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert empresa_propia_id in ids
    assert str(empresa_ajena.id) not in ids


def test_admin_delegado_no_puede_gestionar_usuarios_de_empresa_ajena(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    empresa_ajena = crear_empresa(db, _sufijo())

    resp = client.get(f"/mis-empresas/{empresa_ajena.id}/usuarios", headers=headers)
    assert resp.status_code == 403

    resp = client.post(
        f"/mis-empresas/{empresa_ajena.id}/usuarios",
        json={"email": "no-importa@example.com", "rol": "contador"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_escenario_desde_mis_empresas_sin_cambiar_empresa_activa(client, db):
    """Un admin delegado crea 3 empresas y, SIN pasar por /auth/seleccionar-empresa
    entre medio, le da acceso de contador a un usuario existente en 2 de las 3
    directo desde /mis-empresas/{empresa_id}/usuarios."""
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers_admin = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    ids_empresas = []
    for i in range(3):
        resp = client.post(
            "/empresas",
            json={"razon_social": f"Empresa {i + 1}", "ruc": f"RUC-{_sufijo()}"},
            headers=headers_admin,
        )
        assert resp.status_code == 201, resp.text
        ids_empresas.append(resp.json()["id"])
    empresa_1, empresa_2, _empresa_3 = ids_empresas

    contador = crear_usuario(db, f"contador-{_sufijo()}@example.com")

    for empresa_id in (empresa_1, empresa_2):
        resp = client.post(
            f"/mis-empresas/{empresa_id}/usuarios",
            json={"email": contador.email, "rol": "contador"},
            headers=headers_admin,
        )
        assert resp.status_code == 201, resp.text

    resp = client.post("/auth/login", json={"email": contador.email, "password": "Secreta123!"})
    headers_contador = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get("/auth/empresas", headers=headers_contador)
    ids_contador = {e["empresa_id"] for e in resp.json()}
    assert ids_contador == {empresa_1, empresa_2}


def test_no_se_puede_desactivar_al_unico_admin_de_una_empresa(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin_unico = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vinculo = vincular(db, admin_unico, empresa, "admin")

    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    headers_super = login_y_seleccionar(client, superadmin, empresa)

    resp = client.patch(
        f"/empresas/actual/usuarios/{vinculo.id}", json={"activo": False}, headers=headers_super
    )
    assert resp.status_code == 422
    assert "asigna otro admin" in resp.json()["detail"].lower()

    # Tampoco degradarlo de rol sin desactivarlo -- misma protección.
    resp = client.patch(
        f"/empresas/actual/usuarios/{vinculo.id}", json={"rol": "contador"}, headers=headers_super
    )
    assert resp.status_code == 422


def test_no_se_puede_desactivar_al_unico_admin_via_mis_empresas(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin_unico = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vinculo = vincular(db, admin_unico, empresa, "admin")

    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    resp = client.post("/auth/login", json={"email": superadmin.email, "password": "Secreta123!"})
    headers_super = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.patch(
        f"/mis-empresas/{empresa.id}/usuarios/{vinculo.id}",
        json={"activo": False},
        headers=headers_super,
    )
    assert resp.status_code == 422


def test_si_hay_dos_admins_desactivar_a_uno_funciona(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin_1 = crear_usuario(db, f"admin1-{_sufijo()}@example.com")
    admin_2 = crear_usuario(db, f"admin2-{_sufijo()}@example.com")
    vinculo_1 = vincular(db, admin_1, empresa, "admin")
    vincular(db, admin_2, empresa, "admin")

    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    headers_super = login_y_seleccionar(client, superadmin, empresa)

    resp = client.patch(
        f"/empresas/actual/usuarios/{vinculo_1.id}", json={"activo": False}, headers=headers_super
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False

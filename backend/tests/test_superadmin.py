import uuid

from sqlalchemy import select, text

from app.models import AuditoriaCambio
from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def test_usuario_normal_no_puede_crear_empresas(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)

    resp = client.post(
        "/empresas", json={"razon_social": "Cliente Nuevo", "ruc": f"RUC-{_sufijo()}"}, headers=headers
    )
    assert resp.status_code == 403


def test_superadmin_crea_empresa_y_queda_auditado(client, db):
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    resp = client.post("/auth/login", json={"email": superadmin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    ruc = f"RUC-{_sufijo()}"
    resp = client.post(
        "/empresas",
        json={"razon_social": "Cliente Nuevo S.A.", "nombre_comercial": "Cliente Nuevo", "ruc": ruc, "dv": "12"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["razon_social"] == "Cliente Nuevo S.A."
    assert body["ruc"] == ruc

    # auditoria_cambios tiene RLS FORCE: esta sesión de test (distinta a
    # la del client) necesita app.empresa_actual fijado para poder leer,
    # mismo patrón que conftest.py::crear_empleado.
    db.execute(
        text("SELECT set_config('app.empresa_actual', :eid, false)"), {"eid": body["id"]}
    )
    evento = db.scalar(
        select(AuditoriaCambio).where(
            AuditoriaCambio.tabla_afectada == "empresas",
            AuditoriaCambio.registro_id == uuid.UUID(body["id"]),
        )
    )
    assert evento is not None
    assert evento.accion == "empresa_creada"
    assert evento.usuario_id == superadmin.id


def test_crear_empresa_con_ruc_duplicado_devuelve_409(client, db):
    existente = crear_empresa(db, _sufijo())
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    resp = client.post("/auth/login", json={"email": superadmin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/empresas", json={"razon_social": "Otra", "ruc": existente.ruc}, headers=headers
    )
    assert resp.status_code == 409


def test_superadmin_ve_todas_las_empresas_en_auth_empresas(client, db):
    empresa_ajena = crear_empresa(db, _sufijo())
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    resp = client.post("/auth/login", json={"email": superadmin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.get("/auth/empresas", headers=headers)
    assert resp.status_code == 200
    empresas = resp.json()
    ids = {e["empresa_id"] for e in empresas}
    assert str(empresa_ajena.id) in ids
    assert all(e["rol"] == "superadmin" for e in empresas)


def test_superadmin_entra_a_empresa_ajena_como_admin(client, db):
    empresa_ajena = crear_empresa(db, _sufijo())
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    headers = login_y_seleccionar(client, superadmin, empresa_ajena)

    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["rol_activo"] == "admin"

    # Endpoint admin-only real (require_roles("admin")): confirma que el
    # bypass de superadmin funciona de punta a punta, no solo en el JWT.
    resp = client.get("/auditoria", headers=headers)
    assert resp.status_code == 200


def test_usuario_normal_sigue_sin_poder_entrar_a_empresa_ajena(client, db):
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


# --- Permiso delegado (puede_crear_empresas) ---


def test_admin_delegado_crea_empresa_y_queda_auto_vinculado(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/empresas", json={"razon_social": "Empresa Delegada", "ruc": f"RUC-{_sufijo()}"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    empresa_id = resp.json()["id"]

    # Sin bypass de superadmin: solo puede entrar porque crear_empresa lo
    # vinculó como admin.
    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": empresa_id}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    headers_empresa = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get("/auth/me", headers=headers_empresa)
    assert resp.json()["rol_activo"] == "admin"


def test_admin_delegado_no_puede_gestionar_permisos_de_otros(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.get("/usuarios", headers=headers)
    assert resp.status_code == 403

    resp = client.patch(f"/usuarios/{admin.id}", json={"puede_crear_empresas": False}, headers=headers)
    assert resp.status_code == 403


def test_superadmin_lista_y_togglea_permiso_de_un_admin(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    headers_super = login_y_seleccionar(client, superadmin, empresa)

    resp = client.get("/usuarios", headers=headers_super)
    assert resp.status_code == 200
    fila = next(u for u in resp.json() if u["id"] == str(admin.id))
    assert fila["puede_crear_empresas"] is False

    resp = client.patch(
        f"/usuarios/{admin.id}", json={"puede_crear_empresas": True}, headers=headers_super
    )
    assert resp.status_code == 200
    assert resp.json()["puede_crear_empresas"] is True

    # Ahora el admin (ya con el permiso) puede crear una empresa.
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers_admin = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.post(
        "/empresas", json={"razon_social": "Nueva", "ruc": f"RUC-{_sufijo()}"}, headers=headers_admin
    )
    assert resp.status_code == 201, resp.text


def test_get_usuarios_excluye_usuarios_sin_rol_admin(client, db):
    empresa = crear_empresa(db, _sufijo())
    contador = crear_usuario(db, f"contador-{_sufijo()}@example.com")
    vincular(db, contador, empresa, "contador")
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    headers = login_y_seleccionar(client, superadmin, empresa)

    resp = client.get("/usuarios", headers=headers)
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()}
    assert str(contador.id) not in ids


def test_admin_delegado_no_ve_ni_entra_a_empresa_que_no_creo(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/empresas", json={"razon_social": "Empresa Propia", "ruc": f"RUC-{_sufijo()}"}, headers=headers
    )
    assert resp.status_code == 201
    empresa_ajena = crear_empresa(db, _sufijo())  # otra, no creada por este admin

    resp = client.get("/auth/empresas", headers=headers)
    ids = {e["empresa_id"] for e in resp.json()}
    assert str(empresa_ajena.id) not in ids

    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa_ajena.id)}, headers=headers
    )
    assert resp.status_code == 403


def test_escenario_admin_delegado_con_contadores_selectivos(client, db):
    """Reproduce el ejemplo exacto del usuario: un admin delegado crea 3
    empresas y da acceso de contador de forma independiente por empresa
    -- Contador 1 a las empresas 1 y 2 (no 3), Contador 2 a las empresas
    1 y 3 (no 2). Estos accesos ya son los de usuarios_empresas de
    siempre (POST /empresas/actual/usuarios), sin código nuevo."""
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
    empresa_1, empresa_2, empresa_3 = ids_empresas

    contador_1 = crear_usuario(db, f"contador1-{_sufijo()}@example.com")
    contador_2 = crear_usuario(db, f"contador2-{_sufijo()}@example.com")

    def agregar_contador(empresa_id, contador):
        resp = client.post(
            "/auth/seleccionar-empresa", json={"empresa_id": empresa_id}, headers=headers_admin
        )
        assert resp.status_code == 200, resp.text
        headers_empresa = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        resp = client.post(
            "/empresas/actual/usuarios",
            json={"email": contador.email, "rol": "contador"},
            headers=headers_empresa,
        )
        assert resp.status_code == 201, resp.text

    agregar_contador(empresa_1, contador_1)
    agregar_contador(empresa_2, contador_1)
    agregar_contador(empresa_1, contador_2)
    agregar_contador(empresa_3, contador_2)

    resp = client.post("/auth/login", json={"email": contador_1.email, "password": "Secreta123!"})
    headers_c1 = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get("/auth/empresas", headers=headers_c1)
    ids_c1 = {e["empresa_id"] for e in resp.json()}
    assert ids_c1 == {empresa_1, empresa_2}

    resp = client.post("/auth/login", json={"email": contador_2.email, "password": "Secreta123!"})
    headers_c2 = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get("/auth/empresas", headers=headers_c2)
    ids_c2 = {e["empresa_id"] for e in resp.json()}
    assert ids_c2 == {empresa_1, empresa_3}

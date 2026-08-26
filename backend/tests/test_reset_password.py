import datetime
import uuid

from sqlalchemy import select, text

from app.models import AuditoriaCambio
from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_admin_y_contador(db, client):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    contador = crear_usuario(db, f"contador-{_sufijo()}@example.com")
    vincular(db, contador, empresa, "contador")
    headers_admin = login_y_seleccionar(client, admin, empresa)
    return empresa, admin, contador, headers_admin


def _vinculo_id(client, headers, email):
    resp = client.get("/empresas/actual/usuarios", headers=headers)
    assert resp.status_code == 200, resp.text
    return next(u["id"] for u in resp.json() if u["email"] == email)


def test_admin_resetea_password_de_contador_y_fuerza_cambio(client, db):
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)
    vinculo_id = _vinculo_id(client, headers_admin, contador.email)

    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    password_temporal = body["password_temporal"]
    assert body["expira_en"]

    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    assert resp.status_code == 200, resp.text
    headers_contador = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Bloqueado fuera del allowlist mientras debe_cambiar_password sea true.
    resp = client.get("/auth/empresas", headers=headers_contador)
    assert resp.status_code == 403

    resp = client.get("/auth/me", headers=headers_contador)
    assert resp.status_code == 200, resp.text
    assert resp.json()["usuario"]["debe_cambiar_password"] is True

    resp = client.post(
        "/auth/cambiar-password-temporal",
        json={"password_actual": password_temporal, "password_nueva": "NuevaSegura123"},
        headers=headers_contador,
    )
    assert resp.status_code == 200, resp.text
    headers_contador_nuevo = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Ya no bloquea.
    resp = client.get("/auth/empresas", headers=headers_contador_nuevo)
    assert resp.status_code == 200

    # La temporal vieja ya no sirve; la nueva sí.
    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    assert resp.status_code == 401
    resp = client.post("/auth/login", json={"email": contador.email, "password": "NuevaSegura123"})
    assert resp.status_code == 200


def test_admin_no_puede_resetear_su_propio_password(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    headers = login_y_seleccionar(client, admin, empresa)
    propio_id = _vinculo_id(client, headers, admin.email)

    resp = client.post(f"/empresas/actual/usuarios/{propio_id}/resetear-password", headers=headers)
    assert resp.status_code == 422, resp.text


def test_reset_queda_auditado(client, db):
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)
    vinculo_id = _vinculo_id(client, headers_admin, contador.email)

    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    assert resp.status_code == 200, resp.text

    db.execute(text("SELECT set_config('app.empresa_actual', :eid, false)"), {"eid": str(empresa.id)})
    evento = db.scalar(
        select(AuditoriaCambio).where(
            AuditoriaCambio.tabla_afectada == "usuarios",
            AuditoriaCambio.registro_id == contador.id,
            AuditoriaCambio.accion == "password_reseteado",
        )
    )
    assert evento is not None
    assert evento.usuario_id == admin.id


def test_reset_revoca_refresh_tokens_previos(client, db):
    # Auditoría de seguridad 2026-08-25 (hallazgo A2): el refresh token ya
    # no viaja en el body -- vive en una cookie httpOnly.
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)

    resp = client.post("/auth/login", json={"email": contador.email, "password": "Secreta123!"})
    assert resp.status_code == 200, resp.text
    refresh_previo = client.cookies.get("refresh_token")
    assert refresh_previo is not None

    vinculo_id = _vinculo_id(client, headers_admin, contador.email)
    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    assert resp.status_code == 200, resp.text

    client.cookies.set("refresh_token", refresh_previo)
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_password_temporal_expirada_rechaza_login(client, db):
    empresa = crear_empresa(db, _sufijo())
    contador = crear_usuario(db, f"contador-{_sufijo()}@example.com")
    vincular(db, contador, empresa, "contador")

    contador.debe_cambiar_password = True
    contador.password_temporal_expira = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=1
    )
    db.add(contador)
    db.commit()

    resp = client.post("/auth/login", json={"email": contador.email, "password": "Secreta123!"})
    assert resp.status_code == 401, resp.text


def test_cambiar_password_temporal_rechaza_igual_a_la_actual(client, db):
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)
    vinculo_id = _vinculo_id(client, headers_admin, contador.email)
    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    password_temporal = resp.json()["password_temporal"]

    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    headers_contador = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/cambiar-password-temporal",
        json={"password_actual": password_temporal, "password_nueva": password_temporal},
        headers=headers_contador,
    )
    assert resp.status_code == 422, resp.text


def test_cambiar_password_temporal_valida_longitud_minima(client, db):
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)
    vinculo_id = _vinculo_id(client, headers_admin, contador.email)
    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    password_temporal = resp.json()["password_temporal"]

    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    headers_contador = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/cambiar-password-temporal",
        json={"password_actual": password_temporal, "password_nueva": "corta"},
        headers=headers_contador,
    )
    assert resp.status_code == 422, resp.text


def test_cambiar_password_temporal_rechaza_actual_incorrecta(client, db):
    empresa, admin, contador, headers_admin = _preparar_admin_y_contador(db, client)
    vinculo_id = _vinculo_id(client, headers_admin, contador.email)
    resp = client.post(f"/empresas/actual/usuarios/{vinculo_id}/resetear-password", headers=headers_admin)
    password_temporal = resp.json()["password_temporal"]

    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    headers_contador = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/cambiar-password-temporal",
        json={"password_actual": "incorrecta", "password_nueva": "NuevaSegura123"},
        headers=headers_contador,
    )
    assert resp.status_code == 401, resp.text


def test_superadmin_resetea_password_de_admin(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    superadmin = crear_usuario(db, f"super-{_sufijo()}@example.com", es_superadmin=True)
    resp = client.post("/auth/login", json={"email": superadmin.email, "password": "Secreta123!"})
    headers_super = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(f"/usuarios/{admin.id}/resetear-password", headers=headers_super)
    assert resp.status_code == 200, resp.text
    password_temporal = resp.json()["password_temporal"]

    resp = client.post("/auth/login", json={"email": admin.email, "password": password_temporal})
    assert resp.status_code == 200, resp.text


def test_admin_normal_no_puede_resetear_via_ruta_superadmin(client, db):
    empresa = crear_empresa(db, _sufijo())
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com")
    vincular(db, admin, empresa, "admin")
    otro_admin = crear_usuario(db, f"otro-{_sufijo()}@example.com")
    vincular(db, otro_admin, empresa, "admin")
    headers = login_y_seleccionar(client, admin, empresa)

    resp = client.post(f"/usuarios/{otro_admin.id}/resetear-password", headers=headers)
    assert resp.status_code == 403, resp.text


def test_reset_via_mis_empresas(client, db):
    admin = crear_usuario(db, f"admin-{_sufijo()}@example.com", puede_crear_empresas=True)
    resp = client.post("/auth/login", json={"email": admin.email, "password": "Secreta123!"})
    headers_admin = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/empresas", json={"razon_social": "Propia", "ruc": f"RUC-{_sufijo()}"}, headers=headers_admin
    )
    assert resp.status_code == 201, resp.text
    empresa_id = resp.json()["id"]

    contador = crear_usuario(db, f"contador-{_sufijo()}@example.com")
    resp = client.post(
        f"/mis-empresas/{empresa_id}/usuarios",
        json={"email": contador.email, "rol": "contador"},
        headers=headers_admin,
    )
    assert resp.status_code == 201, resp.text
    vinculo_id = resp.json()["id"]

    resp = client.post(
        f"/mis-empresas/{empresa_id}/usuarios/{vinculo_id}/resetear-password", headers=headers_admin
    )
    assert resp.status_code == 200, resp.text
    password_temporal = resp.json()["password_temporal"]

    resp = client.post("/auth/login", json={"email": contador.email, "password": password_temporal})
    assert resp.status_code == 200, resp.text

import uuid

from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def test_ruc_y_dv_son_campos_independientes_editables(client, db):
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)

    ruc_original = empresa.ruc
    nuevo_ruc = f"155-{_sufijo()}"

    resp = client.patch("/empresas/actual", json={"ruc": nuevo_ruc, "dv": "42"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ruc"] == nuevo_ruc
    assert body["ruc"] != ruc_original
    assert body["dv"] == "42"


def test_ruc_duplicado_entre_empresas_devuelve_409(client, db):
    empresa_a = crear_empresa(db, _sufijo())
    empresa_b = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa_b, "admin")
    headers = login_y_seleccionar(client, usuario, empresa_b)

    resp = client.patch("/empresas/actual", json={"ruc": empresa_a.ruc}, headers=headers)
    assert resp.status_code == 409, resp.text

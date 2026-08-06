import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _headers(db, client) -> dict:
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "consulta")
    return login_y_seleccionar(client, usuario, empresa)


def test_listar_tasas_vigentes_incluye_css_seguro_educativo_decimo(client, db):
    headers = _headers(db, client)
    resp = client.get("/tasas/vigentes", headers=headers)
    assert resp.status_code == 200, resp.text
    # css_empleado es fija, sin fecha_fin -- siempre debe aparecer.
    fila = next(t for t in resp.json() if t["tipo_tasa"] == "css_empleado")
    assert decimal.Decimal(str(fila["tasa"])) == decimal.Decimal("0.0975")


def test_listar_tasas_vigentes_filtra_por_tipo(client, db):
    headers = _headers(db, client)
    resp = client.get("/tasas/vigentes", params={"tipo_tasa": "seguro_educativo_patronal"}, headers=headers)
    assert resp.status_code == 200, resp.text
    filas = resp.json()
    assert len(filas) == 1
    assert decimal.Decimal(str(filas[0]["tasa"])) == decimal.Decimal("0.0150")


def test_listar_tramos_isr(client, db):
    headers = _headers(db, client)
    resp = client.get("/tasas/isr", headers=headers)
    assert resp.status_code == 200, resp.text
    tramos = resp.json()
    assert len(tramos) == 3
    ultimo = next(t for t in tramos if t["monto_hasta"] is None)
    assert decimal.Decimal(str(ultimo["tasa_marginal"])) == decimal.Decimal("0.25")
    assert decimal.Decimal(str(ultimo["impuesto_base"])) == decimal.Decimal("5850.00")


def test_listar_riesgo_profesional_5_clases(client, db):
    headers = _headers(db, client)
    resp = client.get("/tasas/riesgo-profesional", headers=headers)
    assert resp.status_code == 200, resp.text
    clases = {f["clase_riesgo"] for f in resp.json()}
    assert clases == {"I", "II", "III", "IV", "V"}


def test_listar_salario_minimo_filtra_por_region_y_actividad(client, db):
    headers = _headers(db, client)
    # Global/compartida entre tests: se siembra con limpiar=True para
    # no depender de lo que haya dejado otro test (mismo criterio que
    # el resto de la suite, ver test_salario_minimo_avanzado.py).
    crear_salario_minimo(
        db, datetime.date(2020, 1, 1), decimal.Decimal("900.00"), region="Región 1",
        actividad="Comercio al por menor", fecha_fin=None,
    )
    crear_salario_minimo(
        db, datetime.date(2020, 1, 1), decimal.Decimal("1000.00"), region="Región 2",
        actividad="Agricultura", fecha_fin=None, limpiar=False,
    )

    resp = client.get("/tasas/salario-minimo", params={"region": "Región 1"}, headers=headers)
    assert resp.status_code == 200, resp.text
    filas = resp.json()
    assert len(filas) == 1
    assert filas[0]["actividad"] == "Comercio al por menor"

    resp = client.get("/tasas/salario-minimo", params={"actividad": "agricultura"}, headers=headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["region"] == "Región 2"


def test_tasas_no_requieren_rol_admin(client, db):
    # Son informativas -- cualquier rol autenticado puede consultarlas.
    headers = _headers(db, client)  # vinculado como "consulta"
    resp = client.get("/tasas/vigentes", headers=headers)
    assert resp.status_code == 200, resp.text

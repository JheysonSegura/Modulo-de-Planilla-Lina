import base64
import datetime
import decimal
import io
import uuid
import zipfile

from sqlalchemy import text

from app.models import MovimientoPlanilla
from app.services import reportes_service
from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Salario $2,500/mes es el caso de verificación del contador para ISR
# (CLAUDE.md sección 5): bruto anual con décimo $32,500 -> excedente
# $21,500 -> 15% -> $3,225.00/año -> $268.75/mes. Se usa acá para que
# el recibo tenga ISR > 0, además de horas extra, tal como pide el
# criterio de verificación de la Fase 16 ("recibo con horas extra e
# ISR, confirmar que el desglose cuadra con el neto").
SALARIO_BASE = decimal.Decimal("2500.00")
ISR_ESPERADO = decimal.Decimal("268.75")

# Enero (no marzo): así el período es el primero del año calendario
# para este contrato nuevo (isr_numero_periodo_anio=1,
# isr_periodos_restantes_anio=12), igual que el caso de verificación
# del contador en test_isr.py -- 2025-01-06 es lunes.
LUNES = datetime.date(2025, 1, 6)


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client):
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)
    return empresa, headers


def _crear_empleado_con_contrato(client, headers):
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": f"Empleado {_sufijo()}"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Prueba reportes",
            "fecha_inicio": "2025-01-01",
            "salario_base": str(SALARIO_BASE),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _registrar_horas_extra(client, headers, contrato_id):
    resp = client.post(
        f"/contratos/{contrato_id}/horas-extra",
        json={
            "fecha": LUNES.isoformat(),
            "tipo_hora": "diurna",
            "tipo_dia": "ordinario",
            "horas": "2.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generar_planilla_periodo(client, headers):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": "mensual",
            "periodo_inicio": "2025-01-01",
            "periodo_fin": "2025-01-31",
            "fecha_pago": "2025-01-31",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _unico_movimiento(client, headers, planilla_id):
    resp = client.get(f"/planillas/{planilla_id}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimientos = resp.json()
    assert len(movimientos) == 1
    return movimientos[0]


def _preparar_movimiento_con_horas_extra_e_isr(db, client):
    empresa, headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers)
    registro_horas = _registrar_horas_extra(client, headers, contrato_id)
    planilla = _generar_planilla_periodo(client, headers)
    mov = _unico_movimiento(client, headers, planilla["id"])

    assert decimal.Decimal(str(mov["isr_retenido"])) == ISR_ESPERADO
    assert decimal.Decimal(registro_horas["monto_calculado"]) > decimal.Decimal("0")

    return empresa, headers, planilla, mov


def test_armar_recibo_pago_cuadra_con_el_neto_persistido(db, client):
    empresa, headers, planilla, mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    # RLS: db no es la sesión de una request (no pasó por get_db_rls),
    # hay que fijar app.empresa_actual a mano para leer el movimiento
    # directo, mismo patrón que crear_empleado() en conftest.py.
    db.execute(
        text("SELECT set_config('app.empresa_actual', :eid, false)"), {"eid": str(empresa.id)}
    )
    movimiento = db.get(MovimientoPlanilla, uuid.UUID(mov["id"]))

    contexto = reportes_service.armar_recibo_pago(db, movimiento)

    assert contexto["cuadra"] is True
    assert contexto["isr_retenido"] == ISR_ESPERADO
    assert contexto["salario_bruto"] == decimal.Decimal(str(mov["salario_bruto"]))
    assert contexto["salario_neto"] == decimal.Decimal(str(mov["salario_neto"]))
    # Horas extra agrupadas por tipo (Fase 16): una sola fila 'diurna'.
    assert len(contexto["horas_extra_por_tipo"]) == 1
    assert contexto["horas_extra_por_tipo"][0]["tipo_hora"] == "diurna"
    assert contexto["total_horas_extra"] > decimal.Decimal("0")

    # El desglose impreso debe sumar exactamente al neto -- criterio de
    # verificación explícito de la Fase 16.
    total_ingresos = (
        contexto["salario_base_periodo"]
        + contexto["total_horas_extra"]
        + contexto["total_otros_ingresos"]
    )
    assert total_ingresos == contexto["salario_bruto"]
    assert contexto["salario_bruto"] - contexto["total_deducciones"] == contexto["salario_neto"]


def test_recibo_pago_pdf_endpoint(db, client):
    _empresa, headers, planilla, mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    resp = client.get(
        f"/planillas/{planilla['id']}/movimientos/{mov['id']}/recibo?formato=pdf",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_recibo_pago_excel_endpoint(db, client):
    _empresa, headers, planilla, mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    resp = client.get(
        f"/planillas/{planilla['id']}/movimientos/{mov['id']}/recibo?formato=excel",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers["content-type"]
    assert len(resp.content) > 0


def test_recibos_zip_endpoint(db, client):
    _empresa, headers, planilla, mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    resp = client.get(f"/planillas/{planilla['id']}/recibos", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        nombres = zf.namelist()
        assert len(nombres) == 1  # un solo movimiento en esta planilla de prueba
        assert nombres[0].startswith("recibo-pago-")
        assert nombres[0].endswith(".pdf")
        assert zf.read(nombres[0]).startswith(b"%PDF")


def test_exportar_planilla_excel_y_csv(db, client):
    _empresa, headers, planilla, _mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    resp_excel = client.get(f"/planillas/{planilla['id']}/exportar?formato=excel", headers=headers)
    assert resp_excel.status_code == 200, resp_excel.text
    assert "spreadsheetml" in resp_excel.headers["content-type"]

    resp_csv = client.get(f"/planillas/{planilla['id']}/exportar?formato=csv", headers=headers)
    assert resp_csv.status_code == 200, resp_csv.text
    assert resp_csv.headers["content-type"].startswith("text/csv")
    assert b"Salario neto" in resp_csv.content


def test_exportar_planilla_pdf_consolidado(db, client):
    _empresa, headers, planilla, _mov = _preparar_movimiento_con_horas_extra_e_isr(db, client)

    resp = client.get(f"/planillas/{planilla['id']}/exportar?formato=pdf", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_recibo_vacacion_pdf_endpoint(db, client):
    _empresa, headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers)
    _generar_planilla_periodo(client, headers)

    resp = client.post(
        f"/contratos/{contrato_id}/vacaciones-tomadas",
        json={"fecha": "2025-03-31", "dias": "2"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    eventos = client.get(f"/contratos/{contrato_id}/vacaciones-tomadas", headers=headers)
    assert eventos.status_code == 200, eventos.text
    evento_id = eventos.json()[0]["id"]

    resp = client.get(
        f"/contratos/{contrato_id}/vacaciones-tomadas/{evento_id}/recibo?formato=pdf",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_recibo_liquidacion_pdf_endpoint(db, client):
    _empresa, headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers)
    _generar_planilla_periodo(client, headers)

    resp = client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={"motivo": "renuncia_voluntaria", "fecha_terminacion": "2025-04-15"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    liquidacion_id = resp.json()["id"]

    resp = client.get(f"/liquidaciones/{liquidacion_id}/recibo?formato=pdf", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_logo_empresa_subir_y_obtener(db, client):
    _empresa, headers = _preparar_empresa(db, client)

    # PNG 1x1 transparente mínimo válido, suficiente para probar el
    # roundtrip sin depender de un archivo externo.
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    resp = client.put(
        "/empresas/actual/logo",
        files={"archivo": ("logo.png", png_1x1, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tiene_logo"] is True

    resp = client.get("/empresas/actual/logo", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png_1x1


def test_logo_empresa_rechaza_contenido_que_no_coincide_con_el_content_type(db, client):
    # Auditoría de seguridad 2026-08-25 (hallazgo M4): el content_type lo
    # declara el cliente -- esto simula spoofearlo con texto plano.
    _empresa, headers = _preparar_empresa(db, client)
    resp = client.put(
        "/empresas/actual/logo",
        files={"archivo": ("logo.png", b"no soy un png real", "image/png")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def test_logo_empresa_rechaza_svg_con_script_embebido(db, client):
    _empresa, headers = _preparar_empresa(db, client)
    svg_malicioso = b'<svg onload="alert(1)"><script>alert(1)</script></svg>'
    resp = client.put(
        "/empresas/actual/logo",
        files={"archivo": ("logo.svg", svg_malicioso, "image/svg+xml")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text

import datetime
import decimal
import uuid

from app.models import Empresa
from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

PERIODO_INICIO = datetime.date(2025, 3, 1)
PERIODO_FIN = datetime.date(2025, 3, 31)
FECHA_PAGO = datetime.date(2025, 4, 5)


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> tuple[dict, str]:
    # salario_minimo_vigente es global y sin rollback entre tests (ver
    # nota en test_horas_extra.py): se siembra bajo con limpiar=True
    # para no depender de lo que haya dejado otro test.
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)

    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)
    return headers, str(empresa.id)


def _crear_empleado_con_contrato(
    client, headers, fecha_inicio, salario_base, cargo="Operario", tipo_contrato="indefinido"
) -> str:
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
            "tipo_contrato": tipo_contrato,
            "cargo": cargo,
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": str(salario_base),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _registrar_hora_extra(client, headers, contrato_id, fecha, tipo_hora, horas):
    resp = client.post(
        f"/contratos/{contrato_id}/horas-extra",
        json={"fecha": fecha.isoformat(), "tipo_hora": tipo_hora, "horas": str(horas)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _registrar_concepto_pendiente(client, headers, contrato_id, fecha, tipo, codigo, monto):
    resp = client.post(
        f"/contratos/{contrato_id}/conceptos-variables-pendientes",
        json={"fecha": fecha.isoformat(), "tipo": tipo, "codigo": codigo, "monto": str(monto)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generar_planilla(client, headers, tipo, periodo_inicio, periodo_fin, fecha_pago=FECHA_PAGO):
    return client.post(
        "/planillas/generar",
        json={
            "tipo": tipo,
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": fecha_pago.isoformat(),
        },
        headers=headers,
    )


def _movimiento_de(movimientos, contrato_id):
    return next(m for m in movimientos if m["contrato_id"] == contrato_id)


def test_planilla_mensual_con_tres_empleados_distintos(client, db):
    headers, _empresa_id = _preparar_empresa(db, client)

    # Empleado A: salario fijo simple, contrato vigente desde antes del
    # período -> cubre el período completo, sin prorrateo ni variables.
    contrato_a = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 1, 1), "900.00", cargo="Fijo simple"
    )

    # Empleado B: salario 720.00 (valor_hora_ordinaria = 3.00 exacto,
    # igual que en test_horas_extra.py) + horas extra + un bono pendiente.
    contrato_b = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 1, 1), "720.00", cargo="Con variables"
    )
    _registrar_hora_extra(client, headers, contrato_b, datetime.date(2025, 3, 10), "diurna", "2.00")
    _registrar_concepto_pendiente(
        client, headers, contrato_b, datetime.date(2025, 3, 15), "ingreso", "bono", "50.00"
    )

    # Empleado C: contrato que arranca a mitad del período (2025-03-20)
    # -> se prorratea por días reales trabajados (12 días: 20 al 31)
    # sobre salario_diario = 900.00/30 = 30.00 exactos.
    contrato_c = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 3, 20), "900.00", cargo="Ingreso a mitad de mes"
    )

    resp = _generar_planilla(client, headers, "mensual", PERIODO_INICIO, PERIODO_FIN)
    assert resp.status_code == 201, resp.text
    planilla = resp.json()
    assert planilla["estado"] == "borrador"

    resp = client.get(f"/planillas/{planilla['id']}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimientos = resp.json()
    assert len(movimientos) == 3

    # --- Empleado A: fijo simple ---
    mov_a = _movimiento_de(movimientos, contrato_a)
    assert decimal.Decimal(str(mov_a["salario_base_periodo"])) == decimal.Decimal("900.00")
    assert decimal.Decimal(str(mov_a["salario_bruto"])) == decimal.Decimal("900.00")
    assert decimal.Decimal(str(mov_a["css_empleado"])) == decimal.Decimal("87.75")
    assert decimal.Decimal(str(mov_a["seguro_educativo_empleado"])) == decimal.Decimal("11.25")
    assert decimal.Decimal(str(mov_a["css_patronal"])) == decimal.Decimal("119.25")
    assert decimal.Decimal(str(mov_a["seguro_educativo_patronal"])) == decimal.Decimal("13.50")
    assert decimal.Decimal(str(mov_a["riesgo_profesional_patronal"])) == decimal.Decimal("0.00")
    # ISR (Fase 7, método confirmado por el contador 2026-08-04): bruto
    # anual con décimo = 900*13=11700 -> ya supera el exento de 11000
    # (a diferencia de Fase 6, donde 900*12=10800 quedaba exento).
    # impuesto=(11700-11000)*0.15=105.00; periodo=marzo (numero 3 de
    # 12), restantes=10 -> isr=105.00/10=10.50.
    assert decimal.Decimal(str(mov_a["isr_impuesto_anual_proyectado"])) == decimal.Decimal("105.00")
    assert decimal.Decimal(str(mov_a["isr_retenido"])) == decimal.Decimal("10.50")
    assert decimal.Decimal(str(mov_a["salario_neto"])) == decimal.Decimal("790.50")
    assert mov_a["conceptos_variables"] == []

    # --- Empleado B: horas extra + bono ---
    mov_b = _movimiento_de(movimientos, contrato_b)
    assert decimal.Decimal(str(mov_b["salario_base_periodo"])) == decimal.Decimal("720.00")
    # bruto = 720.00 base + 7.50 horas extra (2h * 3.00 * 1.25) + 50.00 bono
    assert decimal.Decimal(str(mov_b["salario_bruto"])) == decimal.Decimal("777.50")
    assert decimal.Decimal(str(mov_b["css_empleado"])) == decimal.Decimal("75.81")
    assert decimal.Decimal(str(mov_b["seguro_educativo_empleado"])) == decimal.Decimal("9.72")
    assert decimal.Decimal(str(mov_b["css_patronal"])) == decimal.Decimal("103.02")
    assert decimal.Decimal(str(mov_b["seguro_educativo_patronal"])) == decimal.Decimal("11.66")
    # Bruto anual con décimo = 720*13=9360, sigue bajo el exento de
    # 11000 (el ISR se anualiza sobre el salario fijo, no sobre las
    # horas extra/bono de este período puntual -- ver Fase 7).
    assert decimal.Decimal(str(mov_b["isr_retenido"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(mov_b["salario_neto"])) == decimal.Decimal("691.97")
    codigos_b = {c["codigo"] for c in mov_b["conceptos_variables"]}
    assert codigos_b == {"hora_extra", "bono"}
    monto_hextra = next(
        c["monto"] for c in mov_b["conceptos_variables"] if c["codigo"] == "hora_extra"
    )
    assert decimal.Decimal(str(monto_hextra)) == decimal.Decimal("7.50")

    # --- Empleado C: prorrateo por ingreso a mitad de período ---
    mov_c = _movimiento_de(movimientos, contrato_c)
    assert decimal.Decimal(str(mov_c["salario_base_periodo"])) == decimal.Decimal("360.00")
    assert decimal.Decimal(str(mov_c["salario_bruto"])) == decimal.Decimal("360.00")
    assert decimal.Decimal(str(mov_c["css_empleado"])) == decimal.Decimal("35.10")
    assert decimal.Decimal(str(mov_c["seguro_educativo_empleado"])) == decimal.Decimal("4.50")
    # El ISR se anualiza sobre el salario_mensual_vigente completo
    # (900.00), no sobre el salario_base_periodo ya prorrateado
    # (360.00). A diferencia del empleado A (contrato vigente desde
    # antes del período), el contrato de C arranca a mitad del propio
    # período fiscal (2025-03-20) -- corrección 2026-08-18, confirmada
    # por el contador: el conteo de períodos para prorratear el ISR
    # parte de su propia fecha de inicio, no de la posición absoluta en
    # el calendario. Por eso su primer mes ya vale período 1 de 12 (12
    # cuotas completas por delante), no período 3 de 12 como A:
    # isr=105.00/12=8.75, no 10.50.
    assert decimal.Decimal(str(mov_c["isr_retenido"])) == decimal.Decimal("8.75")
    assert decimal.Decimal(str(mov_c["salario_neto"])) == decimal.Decimal("311.65")


def test_riesgo_profesional_patronal_segun_clase_riesgo_de_la_empresa(client, db):
    headers, empresa_id = _preparar_empresa(db, client)

    # clase_riesgo es un campo manual (Decreto de Gabinete N.68/1970,
    # la CSS se lo asigna a la empresa) -- no hay endpoint para
    # editarlo todavía, se setea directo en BD como en el resto de la
    # suite cuando no hay endpoint público.
    empresa = db.get(Empresa, uuid.UUID(empresa_id))
    empresa.clase_riesgo = "III"
    db.commit()

    contrato = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 1, 1), "900.00", cargo="Clase III"
    )

    resp = _generar_planilla(client, headers, "mensual", PERIODO_INICIO, PERIODO_FIN)
    assert resp.status_code == 201, resp.text
    planilla = resp.json()

    resp = client.get(f"/planillas/{planilla['id']}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    mov = _movimiento_de(resp.json(), contrato)

    # Clase III: grado promedio 30 x 0.0007 = 0.0210 -> 900.00*0.0210=18.90
    assert decimal.Decimal(str(mov["riesgo_profesional_patronal"])) == decimal.Decimal("18.90")


def test_generar_planilla_duplicada_para_el_mismo_periodo_es_rechazada(client, db):
    headers, _empresa_id = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1), "900.00")

    primera = _generar_planilla(client, headers, "mensual", PERIODO_INICIO, PERIODO_FIN)
    assert primera.status_code == 201, primera.text

    segunda = _generar_planilla(client, headers, "mensual", PERIODO_INICIO, PERIODO_FIN)
    assert segunda.status_code == 409, segunda.text


def test_planilla_quincenal_paga_medio_mes_comercial_no_dias_calendario_reales(client, db):
    headers, _empresa_id = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1), "900.00")

    # Segunda quincena de marzo 2025: 16 días calendario reales
    # (16-31), pero el mes comercial de 30 días dice que una quincena
    # completa son exactamente 15/30 = la mitad del salario mensual,
    # nunca 16/30 -- CLAUDE.md sección 5, "Lógica ya cerrada".
    periodo_inicio = datetime.date(2025, 3, 16)
    periodo_fin = datetime.date(2025, 3, 31)

    resp = _generar_planilla(client, headers, "quincenal", periodo_inicio, periodo_fin)
    assert resp.status_code == 201, resp.text
    planilla = resp.json()

    resp = client.get(f"/planillas/{planilla['id']}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    movimientos = resp.json()
    assert len(movimientos) == 1
    assert decimal.Decimal(str(movimientos[0]["salario_base_periodo"])) == decimal.Decimal("450.00")
    assert decimal.Decimal(str(movimientos[0]["salario_base_periodo"])) != decimal.Decimal("480.00")


def test_listar_planillas_devuelve_solo_las_de_la_empresa_activa(client, db):
    headers_a, _ = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers_a, datetime.date(2025, 1, 1), "900.00")
    _generar_planilla(client, headers_a, "mensual", PERIODO_INICIO, PERIODO_FIN)

    headers_b, _ = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers_b, datetime.date(2025, 1, 1), "900.00")
    _generar_planilla(client, headers_b, "mensual", PERIODO_INICIO, PERIODO_FIN)

    resp = client.get("/planillas", headers=headers_a)
    assert resp.status_code == 200, resp.text
    planillas = resp.json()
    assert len(planillas) == 1
    assert planillas[0]["periodo_inicio"] == PERIODO_INICIO.isoformat()


def test_listar_planillas_filtra_por_estado_y_tipo(client, db):
    headers, _ = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1), "900.00")

    resp = _generar_planilla(client, headers, "mensual", PERIODO_INICIO, PERIODO_FIN)
    planilla_id = resp.json()["id"]
    resp = _generar_planilla(
        client, headers, "quincenal", datetime.date(2025, 4, 1), datetime.date(2025, 4, 15)
    )
    assert resp.status_code == 201, resp.text

    resp = client.get("/planillas", params={"tipo": "mensual"}, headers=headers)
    assert [p["id"] for p in resp.json()] == [planilla_id]

    resp = client.post(f"/planillas/{planilla_id}/aprobar", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.get("/planillas", params={"estado": "procesada"}, headers=headers)
    assert [p["id"] for p in resp.json()] == [planilla_id]

    resp = client.get("/planillas", params={"estado": "borrador"}, headers=headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] != planilla_id

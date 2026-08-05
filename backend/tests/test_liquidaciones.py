import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Salario 1200.00/mes -> salario_diario=40.00, salario_semanal=280.00,
# igual criterio de números redondos que test_decimo.py/test_vacaciones.py.
SALARIO = "1200.00"


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> dict:
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return login_y_seleccionar(client, usuario, empresa)


def _crear_empleado_con_contrato(
    client,
    headers,
    fecha_inicio,
    tipo_contrato="indefinido",
    fecha_fin_pactada=None,
    salario_base=SALARIO,
):
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": f"Empleado {_sufijo()}"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    body = {
        "tipo_contrato": tipo_contrato,
        "cargo": "Prueba liquidacion",
        "fecha_inicio": fecha_inicio.isoformat(),
        "salario_base": str(salario_base),
    }
    if fecha_fin_pactada is not None:
        body["fecha_fin_pactada"] = fecha_fin_pactada.isoformat()

    resp = client.post(f"/empleados/{empleado_id}/contratos", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _generar_planilla(client, headers, tipo, periodo_inicio, periodo_fin):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": tipo,
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generar_liquidacion(client, headers, contrato_id, motivo, fecha_terminacion):
    return client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={"motivo": motivo, "fecha_terminacion": fecha_terminacion.isoformat()},
        headers=headers,
    )


def test_renuncia_voluntaria_sin_indemnizacion_ni_preaviso(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    # fecha_terminacion (30-ene) cae ANTES del cierre de la única
    # planilla generada (31-ene) -> ya está todo pagado, salario
    # pendiente = 0. También cae fuera de la ventana Art.149/226 (que
    # exige periodo_fin <= fecha_terminacion) -> cae al fallback de
    # salario_base vigente para prima de antigüedad.
    resp = _generar_liquidacion(
        client, headers, contrato_id, "renuncia_voluntaria", datetime.date(2025, 1, 30)
    )
    assert resp.status_code == 201, resp.text
    liq = resp.json()

    assert decimal.Decimal(str(liq["salario_pendiente"])) == decimal.Decimal("0.00")
    # décimo y vacaciones: 30 días (1-30 ene) / 11 * 40.00 = 109.0909... -> 109.09
    assert decimal.Decimal(str(liq["decimo_proporcional"])) == decimal.Decimal("109.09")
    assert decimal.Decimal(str(liq["vacaciones_pendientes"])) == decimal.Decimal("109.09")
    # prima antigüedad: (30/365) * (1200/30*7) = 23.0136... -> 23.01
    assert decimal.Decimal(str(liq["prima_antiguedad"])) == decimal.Decimal("23.01")
    assert decimal.Decimal(str(liq["indemnizacion"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq["preaviso"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq["monto_total"])) == decimal.Decimal("241.19")
    assert liq["estado"] == "borrador"


def test_despido_justificado_igual_que_renuncia_voluntaria(client, db):
    # Confirma que la distinción real es la CAUSA (justificada vs no),
    # no quién inició la separación: mismo escenario exacto que la
    # renuncia voluntaria, sin indemnización ni preaviso tampoco.
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    resp = _generar_liquidacion(
        client, headers, contrato_id, "despido_justificado", datetime.date(2025, 1, 30)
    )
    assert resp.status_code == 201, resp.text
    liq = resp.json()

    assert decimal.Decimal(str(liq["indemnizacion"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq["preaviso"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq["monto_total"])) == decimal.Decimal("241.19")


def test_despido_injustificado_trae_indemnizacion_y_preaviso(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    # fecha_terminacion (15-feb) cae DESPUES del cierre de la planilla
    # de enero (31-ene): el movimiento SI entra en las ventanas de
    # Art. 149/226, y quedan 15 dias de febrero como salario pendiente.
    resp = _generar_liquidacion(
        client, headers, contrato_id, "despido_injustificado", datetime.date(2025, 2, 15)
    )
    assert resp.status_code == 201, resp.text
    liq = resp.json()

    # 15 dias (1-15 feb) * 40.00
    assert decimal.Decimal(str(liq["salario_pendiente"])) == decimal.Decimal("600.00")
    # decimo/vacaciones: 46 dias (1-ene a 15-feb) / 11 * 40.00 = 167.2727... -> 167.27
    assert decimal.Decimal(str(liq["decimo_proporcional"])) == decimal.Decimal("167.27")
    assert decimal.Decimal(str(liq["vacaciones_pendientes"])) == decimal.Decimal("167.27")
    # prima antigüedad: promedio real (1 mes de movimientos) = 1200.00/mes
    # -> (46/365) * (1200/30*7) = 23.0136... -> 23.01
    assert decimal.Decimal(str(liq["prima_antiguedad"])) == decimal.Decimal("23.01")
    # indemnizacion Art.225-C: anios=46/365 (<=10) -> semanas=anios*3.4;
    # salario base Art.149 = max(1200/6, 1200) = 1200 -> semanal=280.00
    assert decimal.Decimal(str(liq["indemnizacion"])) == decimal.Decimal("119.98")
    # preaviso: 30 * 40.00
    assert decimal.Decimal(str(liq["preaviso"])) == decimal.Decimal("1200.00")
    assert decimal.Decimal(str(liq["monto_total"])) == decimal.Decimal("2277.53")

    resp = client.get(f"/contratos/{contrato_id}/liquidaciones", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_despido_injustificado_es_mas_que_renuncia_voluntaria(client, db):
    # Verificación directa de que los conceptos difieren: mismo
    # escenario en dos empresas distintas (una planilla mensual cubre
    # a toda la empresa, no se puede repetir el mismo período dos
    # veces en la misma empresa), solo cambia el motivo -> el despido
    # injustificado debe traer indemnización + preaviso que la
    # renuncia voluntaria no trae.
    headers_a = _preparar_empresa(db, client)
    contrato_a = _crear_empleado_con_contrato(client, headers_a, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers_a, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    resp_a = _generar_liquidacion(
        client, headers_a, contrato_a, "renuncia_voluntaria", datetime.date(2025, 2, 15)
    )
    assert resp_a.status_code == 201, resp_a.text

    headers_b = _preparar_empresa(db, client)
    contrato_b = _crear_empleado_con_contrato(client, headers_b, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers_b, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
    resp_b = _generar_liquidacion(
        client, headers_b, contrato_b, "despido_injustificado", datetime.date(2025, 2, 15)
    )
    assert resp_b.status_code == 201, resp_b.text

    liq_a, liq_b = resp_a.json(), resp_b.json()
    assert decimal.Decimal(str(liq_a["indemnizacion"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq_a["preaviso"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq_b["indemnizacion"])) > decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq_b["preaviso"])) > decimal.Decimal("0.00")
    assert decimal.Decimal(str(liq_b["monto_total"])) > decimal.Decimal(str(liq_a["monto_total"]))
    # El resto de los conceptos (salario pendiente, décimo, vacaciones,
    # prima antigüedad) debe coincidir exacto entre ambos: la única
    # diferencia real es la causa.
    for campo in ("salario_pendiente", "decimo_proporcional", "vacaciones_pendientes", "prima_antiguedad"):
        assert decimal.Decimal(str(liq_a[campo])) == decimal.Decimal(str(liq_b[campo])), campo


def test_contrato_definido_terminado_antes_de_tiempo_art_227(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(
        client,
        headers,
        datetime.date(2025, 1, 1),
        tipo_contrato="definido",
        fecha_fin_pactada=datetime.date(2025, 12, 31),
    )
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    resp = _generar_liquidacion(
        client, headers, contrato_id, "despido_injustificado", datetime.date(2025, 2, 15)
    )
    assert resp.status_code == 201, resp.text
    liq = resp.json()

    # Sin prima de antigüedad: Art. 224 solo aplica a indefinidos.
    assert decimal.Decimal(str(liq["prima_antiguedad"])) == decimal.Decimal("0.00")
    # Art. 227: salarios del tiempo restante del plazo. 319 dias
    # (15-feb a 31-dic-2025) * 40.00 = 12,760.00.
    assert decimal.Decimal(str(liq["indemnizacion"])) == decimal.Decimal("12760.00")
    assert decimal.Decimal(str(liq["preaviso"])) == decimal.Decimal("1200.00")
    assert decimal.Decimal(str(liq["monto_total"])) == decimal.Decimal("14894.54")


def test_contrato_por_obra_determinada_sin_fecha_fin_rechaza_indemnizacion(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(
        client, headers, datetime.date(2025, 1, 1), tipo_contrato="obra_determinada"
    )
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    resp = _generar_liquidacion(
        client, headers, contrato_id, "despido_injustificado", datetime.date(2025, 2, 15)
    )
    assert resp.status_code == 422, resp.text


def test_generar_liquidacion_termina_el_contrato(client, db):
    headers = _preparar_empresa(db, client)
    contrato_id = _crear_empleado_con_contrato(client, headers, datetime.date(2025, 1, 1))
    _generar_planilla(client, headers, "mensual", datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))

    resp = _generar_liquidacion(
        client, headers, contrato_id, "mutuo_acuerdo", datetime.date(2025, 2, 15)
    )
    assert resp.status_code == 201, resp.text

    resp_contrato = client.get(f"/contratos/{contrato_id}", headers=headers)
    assert resp_contrato.status_code == 200, resp_contrato.text
    contrato = resp_contrato.json()
    assert contrato["estado"] == "terminado"
    assert contrato["fecha_fin_real"] == "2025-02-15"
    assert contrato["motivo_terminacion"] == "mutuo_acuerdo"

    # Segunda liquidación sobre el mismo contrato ya terminado -> 409.
    resp2 = _generar_liquidacion(
        client, headers, contrato_id, "renuncia_voluntaria", datetime.date(2025, 3, 1)
    )
    assert resp2.status_code == 409, resp2.text

import datetime
import decimal
import uuid

from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Salario elegido para que valor_hora_ordinaria = 720.00 / 30 / 8 = 3.00
# exactos, y así los montos esperados en los tests no arrastren
# redondeos que compliquen las aserciones.
SALARIO_BASE = decimal.Decimal("720.00")
VALOR_HORA_ORDINARIA = decimal.Decimal("3.00")

# 2025-03-03 es lunes (semana ISO 2025-W10: lunes 03-03 a domingo 03-09).
# Tiene que caer en o después de 2025-01-01, que es la fecha_inicio con
# la que la migración 0010 siembra los recargos de horas extra en
# tasas_vigentes.
LUNES = datetime.date(2025, 3, 3)
MARTES = datetime.date(2025, 3, 4)
MIERCOLES = datetime.date(2025, 3, 5)
JUEVES = datetime.date(2025, 3, 6)
DOMINGO = datetime.date(2025, 3, 9)


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_contrato(db, client) -> tuple[dict, str]:
    # salario_minimo_vigente es una tabla global sin rollback entre
    # tests: se siembra explícitamente por debajo de SALARIO_BASE con
    # limpiar=True para no depender de lo que haya dejado otro test.
    crear_salario_minimo(
        db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None
    )

    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado de prueba"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": "indefinido",
            "cargo": "Operario",
            "fecha_inicio": "2024-01-01",
            "salario_base": str(SALARIO_BASE),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    contrato_id = resp.json()["id"]
    return headers, contrato_id


def _registrar(client, headers, contrato_id, fecha, tipo_hora, horas, tipo_dia="ordinario"):
    resp = client.post(
        f"/contratos/{contrato_id}/horas-extra",
        json={
            "fecha": fecha.isoformat(),
            "tipo_hora": tipo_hora,
            "tipo_dia": tipo_dia,
            "horas": str(horas),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _listar(client, headers, contrato_id):
    resp = client.get(f"/contratos/{contrato_id}/horas-extra", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_hora_extra_diurna_simple(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    registro = _registrar(client, headers, contrato_id, LUNES, "diurna", "2.00")

    assert decimal.Decimal(str(registro["factor_tipo_hora"])) == decimal.Decimal("0.2500")
    assert decimal.Decimal(str(registro["factor_tipo_dia"])) == decimal.Decimal("0.0000")
    assert decimal.Decimal(str(registro["horas_dentro_limite"])) == decimal.Decimal("2.00")
    assert decimal.Decimal(str(registro["horas_exceso_limite"])) == decimal.Decimal("0.00")
    # 2h * 3.00 * 1.25 = 7.50
    assert decimal.Decimal(str(registro["monto_calculado"])) == decimal.Decimal("7.50")


def test_hora_extra_nocturna(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    registro = _registrar(client, headers, contrato_id, LUNES, "nocturna", "2.00")

    assert decimal.Decimal(str(registro["factor_tipo_hora"])) == decimal.Decimal("0.5000")
    # 2h * 3.00 * 1.50 = 9.00
    assert decimal.Decimal(str(registro["monto_calculado"])) == decimal.Decimal("9.00")


def test_hora_extra_nocturna_en_domingo_es_cascada_multiplicativa_no_sumada(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    registro = _registrar(
        client, headers, contrato_id, DOMINGO, "nocturna", "2.00", tipo_dia="domingo_descanso"
    )

    assert decimal.Decimal(str(registro["factor_tipo_hora"])) == decimal.Decimal("0.5000")
    assert decimal.Decimal(str(registro["factor_tipo_dia"])) == decimal.Decimal("0.5000")
    # Cascada: 2h * 3.00 * 1.5 * 1.5 = 13.50 (NO 2h * 3.00 * 2.0 = 12.00)
    assert decimal.Decimal(str(registro["monto_calculado"])) == decimal.Decimal("13.50")
    assert decimal.Decimal(str(registro["monto_calculado"])) != decimal.Decimal("12.00")


def test_hora_extra_en_feriado(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    registro = _registrar(
        client, headers, contrato_id, LUNES, "diurna", "2.00", tipo_dia="feriado_duelo_nacional"
    )

    assert decimal.Decimal(str(registro["factor_tipo_dia"])) == decimal.Decimal("1.5000")
    # 2h * 3.00 * 1.25 * 2.5 = 18.75
    assert decimal.Decimal(str(registro["monto_calculado"])) == decimal.Decimal("18.75")


def test_exceso_sobre_limite_semanal_de_9h(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    # 3h en cada uno de 3 días distintos de la misma semana ISO = 9h,
    # todas dentro del límite (ni el tope diario ni el semanal se
    # exceden todavía).
    _registrar(client, headers, contrato_id, LUNES, "diurna", "3.00")
    _registrar(client, headers, contrato_id, MARTES, "diurna", "3.00")
    _registrar(client, headers, contrato_id, MIERCOLES, "diurna", "3.00")

    # La 4a hora de la semana (día nuevo, tope diario libre) ya no cabe
    # en el cupo semanal de 9h: 100% exceso, con el +75% adicional del
    # Art. 36 en cascada sobre su propio recargo de tipo_hora.
    registro = _registrar(client, headers, contrato_id, JUEVES, "diurna", "1.00")

    assert decimal.Decimal(str(registro["horas_dentro_limite"])) == decimal.Decimal("0.00")
    assert decimal.Decimal(str(registro["horas_exceso_limite"])) == decimal.Decimal("1.00")
    assert decimal.Decimal(str(registro["factor_exceso_limite"])) == decimal.Decimal("0.7500")
    # 1h * 3.00 * 1.25 * 1.75 = 6.5625 -> redondeado a 6.56
    assert decimal.Decimal(str(registro["monto_calculado"])) == decimal.Decimal("6.56")


def test_tope_diario_se_reparte_en_orden_de_registro_sin_importar_el_tipo(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    # 2h diurna registradas primero: caben completas en el cupo de 3h/día.
    primera = _registrar(client, headers, contrato_id, LUNES, "diurna", "2.00")
    assert decimal.Decimal(str(primera["horas_dentro_limite"])) == decimal.Decimal("2.00")
    assert decimal.Decimal(str(primera["horas_exceso_limite"])) == decimal.Decimal("0.00")

    # 2h nocturna registradas después, mismo día: solo queda 1h de cupo
    # diario: 1h dentro (recargo nocturno normal), 1h de exceso (recargo
    # nocturno + el adicional del Art. 36 en cascada) -- el excedente
    # cae en este segundo renglón, sin importar que sea de otro tipo_hora.
    segunda = _registrar(client, headers, contrato_id, LUNES, "nocturna", "2.00")
    assert decimal.Decimal(str(segunda["horas_dentro_limite"])) == decimal.Decimal("1.00")
    assert decimal.Decimal(str(segunda["horas_exceso_limite"])) == decimal.Decimal("1.00")
    # dentro: 1h * 3.00 * 1.5 = 4.50 ; exceso: 1h * 3.00 * 1.5 * 1.75 = 7.875 -> 7.88
    assert decimal.Decimal(str(segunda["monto_dentro_limite"])) == decimal.Decimal("4.50")
    assert decimal.Decimal(str(segunda["monto_exceso_limite"])) == decimal.Decimal("7.88")


def test_registro_retroactivo_recalcula_toda_la_semana(client, db):
    headers, contrato_id = _preparar_contrato(db, client)

    # Miércoles y jueves, 3h cada uno, registrados primero: ambos caben
    # completos (6h acumuladas en la semana, bajo el tope de 9h).
    _registrar(client, headers, contrato_id, MIERCOLES, "diurna", "3.00")
    jueves_antes = _registrar(client, headers, contrato_id, JUEVES, "diurna", "3.00")
    assert decimal.Decimal(str(jueves_antes["horas_dentro_limite"])) == decimal.Decimal("3.00")
    assert decimal.Decimal(str(jueves_antes["horas_exceso_limite"])) == decimal.Decimal("0.00")

    # Se captura tarde el lunes de la MISMA semana con 4h: al reordenar
    # por fecha (lunes queda primero), la semana ahora suma
    # 4 + 3 + 3 = 10h, así que el jueves -que ya estaba calculado- debe
    # perder 1h de su cupo y pasar a tener exceso.
    _registrar(client, headers, contrato_id, LUNES, "diurna", "4.00")

    registros = _listar(client, headers, contrato_id)
    jueves_recalculado = next(r for r in registros if r["fecha"] == JUEVES.isoformat())
    assert decimal.Decimal(str(jueves_recalculado["horas_dentro_limite"])) == decimal.Decimal("2.00")
    assert decimal.Decimal(str(jueves_recalculado["horas_exceso_limite"])) == decimal.Decimal("1.00")

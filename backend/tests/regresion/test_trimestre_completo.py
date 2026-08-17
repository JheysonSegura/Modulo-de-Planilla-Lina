"""Suite de regresión de un trimestre completo de nómina (Fase 17 -- testing
integral). Ver FASE17-plan-testing-integral.txt (raíz del repo) y
backend/tests/regresion/README.md para el diseño completo del escenario.

Arma UNA sola vez por módulo (fixture `_escenario`, scope="module") un
trimestre real de 6 quincenas para 5 empleados que aíslan cada uno un
concepto: salario fijo con ISR (Ana), horas extra (Bruno), ausencia con
justificación médica (Carla), ausencia injustificada (Diego), y una
liquidación a mitad de período (Elena) -- más el pago de décimo del final
del cuatrimestre. Cada test_* de este archivo solo lee ese resultado ya
construido y compara una porción contra fixtures_trimestre.ESPERADOS.

Si algún valor de ESPERADOS todavía está en None (pendiente de validación
del contador), el test correspondiente se salta con pytest.skip -- pero la
construcción del escenario (los 5 contratos, las 6 planillas, el décimo, la
liquidación) SÍ corre siempre, así que un pytest en verde/skip ya confirma
que el flujo completo no rompe con 4xx/5xx, aunque los montos exactos
todavía no estén verificados.
"""

import datetime
import decimal
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import deps as deps_module
from app.main import app
from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

from .fixtures_trimestre import (
    ANA,
    BRUNO,
    CARLA,
    DECIMO_REQUEST,
    DIEGO,
    ELENA,
    ESPERADOS,
    FECHA_INICIO_CONTRATOS,
    QUINCENAS,
)


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


# --- Fixtures locales de sesión/cliente, scope="module" --------------------
# `db`/`client` en conftest.py son function-scoped (una transacción/cliente
# por test) -- acá se necesitan compartidos por todo el módulo porque el
# escenario completo se arma una sola vez. Mismo patrón que conftest.py,
# solo que reusando `engine`/`SessionTest` (session-scoped, sí compatibles).


@pytest.fixture(scope="module")
def db(SessionTest):
    session = SessionTest()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client(SessionTest):
    def override_get_db():
        session = SessionTest()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- Helpers de request, mismo estilo que test_planillas.py ----------------


def _crear_empleado_con_contrato(client, headers, perfil: dict) -> str:
    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": perfil["nombre"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    resp = client.post(
        f"/empleados/{empleado_id}/contratos",
        json={
            "tipo_contrato": perfil["tipo_contrato"],
            "cargo": "Operario",
            "fecha_inicio": FECHA_INICIO_CONTRATOS.isoformat(),
            "salario_base": perfil["salario_base"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _registrar_hora_extra(client, headers, contrato_id, evento: dict) -> dict:
    resp = client.post(
        f"/contratos/{contrato_id}/horas-extra",
        json={
            "fecha": evento["fecha"].isoformat(),
            "tipo_hora": evento["tipo_hora"],
            "tipo_dia": evento["tipo_dia"],
            "horas": evento["horas"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _registrar_ausencia(client, headers, contrato_id, ausencia: dict) -> dict:
    resp = client.post(
        f"/contratos/{contrato_id}/ausencias",
        json={
            "tipo": ausencia["tipo"],
            "fecha_desde": ausencia["fecha_desde"].isoformat(),
            "fecha_hasta": ausencia["fecha_hasta"].isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generar_planilla(client, headers, periodo_inicio, periodo_fin, fecha_pago) -> dict:
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": "quincenal",
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": fecha_pago.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _movimientos(client, headers, planilla_id) -> list[dict]:
    resp = client.get(f"/planillas/{planilla_id}/movimientos", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _liquidar(client, headers, contrato_id, liquidacion: dict) -> dict:
    resp = client.post(
        f"/contratos/{contrato_id}/liquidacion",
        json={
            "motivo": liquidacion["motivo"],
            "fecha_terminacion": liquidacion["fecha_terminacion"].isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _provision_abierta(client, headers, contrato_id) -> dict:
    resp = client.get(f"/contratos/{contrato_id}/provisiones-vacaciones", headers=headers)
    assert resp.status_code == 200, resp.text
    return next(p for p in resp.json() if p["estado"] == "abierto")


def _verificar(nombre_bloque: str, esperado: dict, actual: dict) -> None:
    faltantes = [campo for campo, valor in esperado.items() if valor is None]
    if faltantes:
        pytest.skip(
            f"{nombre_bloque}: fixture pendiente de validación contable "
            f"({', '.join(faltantes)}) -- ver fixtures_trimestre.py"
        )
    for campo, valor_esperado in esperado.items():
        assert decimal.Decimal(str(actual[campo])) == decimal.Decimal(str(valor_esperado)), (
            f"{nombre_bloque}.{campo}: esperado {valor_esperado}, obtuvo {actual[campo]}"
        )


# --- Construcción del escenario (una sola vez por módulo) ------------------


@pytest.fixture(scope="module")
def _escenario(db, client):
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)

    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"regresion-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    headers = login_y_seleccionar(client, usuario, empresa)

    contratos = {
        "ana": _crear_empleado_con_contrato(client, headers, ANA),
        "bruno": _crear_empleado_con_contrato(client, headers, BRUNO),
        "carla": _crear_empleado_con_contrato(client, headers, CARLA),
        "diego": _crear_empleado_con_contrato(client, headers, DIEGO),
        "elena": _crear_empleado_con_contrato(client, headers, ELENA),
    }

    horas_extra_registros = {}
    claves_horas_extra = ["q2_diurna_ordinario", "q4_nocturna_ordinario", "q6_diurna_domingo_descanso"]
    for clave, evento in zip(claves_horas_extra, BRUNO["horas_extra"]):
        horas_extra_registros[clave] = _registrar_hora_extra(client, headers, contratos["bruno"], evento)

    _registrar_ausencia(client, headers, contratos["carla"], CARLA["ausencia"])
    _registrar_ausencia(client, headers, contratos["diego"], DIEGO["ausencia"])

    movimientos_por_empleado = {clave: [] for clave in contratos}
    liquidacion_elena = None

    for idx, (periodo_inicio, periodo_fin, fecha_pago) in enumerate(QUINCENAS):
        planilla = _generar_planilla(client, headers, periodo_inicio, periodo_fin, fecha_pago)
        movs = _movimientos(client, headers, planilla["id"])
        for clave, contrato_id in contratos.items():
            mov = next((m for m in movs if m["contrato_id"] == contrato_id), None)
            if mov is not None:
                movimientos_por_empleado[clave].append(mov)

        if idx == 1:  # justo tras Q2: Elena se liquida a mitad del trimestre
            liquidacion_elena = _liquidar(client, headers, contratos["elena"], ELENA["liquidacion"])

    decimo_planilla = client.post("/planillas/generar-decimo", json=DECIMO_REQUEST, headers=headers)
    assert decimo_planilla.status_code == 201, decimo_planilla.text
    decimo_movs = _movimientos(client, headers, decimo_planilla.json()["id"])
    decimo_por_empleado = {
        clave: next(m for m in decimo_movs if m["contrato_id"] == contratos[clave])
        for clave in ("ana", "bruno", "carla", "diego")
    }

    return {
        "contratos": contratos,
        "movimientos_por_empleado": movimientos_por_empleado,
        "horas_extra_registros": horas_extra_registros,
        "liquidacion_elena": liquidacion_elena,
        "decimo_por_empleado": decimo_por_empleado,
        "provision_carla": _provision_abierta(client, headers, contratos["carla"]),
        "provision_diego": _provision_abierta(client, headers, contratos["diego"]),
    }


# --- Tests -------------------------------------------------------------


def _campos_salario(mov: dict) -> dict:
    return {
        "salario_bruto": mov["salario_bruto"],
        "css_empleado": mov["css_empleado"],
        "seguro_educativo_empleado": mov["seguro_educativo_empleado"],
        "isr_retenido": mov["isr_retenido"],
        "salario_neto": mov["salario_neto"],
    }


def test_ana_quincena_fija(_escenario):
    movimientos = _escenario["movimientos_por_empleado"]["ana"]
    assert len(movimientos) == 6
    for idx, mov in enumerate(movimientos):
        _verificar(f"ana_quincena_base (Q{idx + 1})", ESPERADOS["ana_quincena_base"], _campos_salario(mov))


def test_bruno_quincenas_sin_horas_extra(_escenario):
    movimientos = _escenario["movimientos_por_empleado"]["bruno"]
    for idx in (0, 2, 4):  # Q1, Q3, Q5
        _verificar(
            f"bruno_quincena_base (Q{idx + 1})",
            ESPERADOS["bruno_quincena_base"],
            _campos_salario(movimientos[idx]),
        )


@pytest.mark.parametrize(
    "idx_quincena,clave_esperado",
    [(1, "q2_diurna_ordinario"), (3, "q4_nocturna_ordinario"), (5, "q6_diurna_domingo_descanso")],
)
def test_bruno_horas_extra(_escenario, idx_quincena, clave_esperado):
    registro = _escenario["horas_extra_registros"][clave_esperado]
    mov = _escenario["movimientos_por_empleado"]["bruno"][idx_quincena]
    actual = {
        "monto_calculado_registro": registro["monto_calculado"],
        "salario_bruto_quincena": mov["salario_bruto"],
        "isr_retenido_quincena": mov["isr_retenido"],
        "salario_neto_quincena": mov["salario_neto"],
    }
    _verificar(f"bruno_horas_extra.{clave_esperado}", ESPERADOS["bruno_horas_extra"][clave_esperado], actual)


def test_carla_y_diego_quincena_no_se_ve_afectada_por_la_ausencia(_escenario):
    for clave in ("carla", "diego"):
        movimientos = _escenario["movimientos_por_empleado"][clave]
        assert len(movimientos) == 6
        for idx, mov in enumerate(movimientos):
            _verificar(
                f"quincena_base_800 ({clave}, Q{idx + 1})",
                ESPERADOS["quincena_base_800"],
                _campos_salario(mov),
            )


def test_carla_ausencia_medica_no_descuenta_vacaciones(_escenario):
    provision = _escenario["provision_carla"]
    _verificar(
        "carla_provision_vacaciones_final",
        ESPERADOS["carla_provision_vacaciones_final"],
        {"dias_acumulados": provision["dias_acumulados"], "monto_provisionado": provision["monto_provisionado"]},
    )


def test_diego_ausencia_injustificada_descuenta_vacaciones(_escenario):
    provision = _escenario["provision_diego"]
    _verificar(
        "diego_provision_vacaciones_final",
        ESPERADOS["diego_provision_vacaciones_final"],
        {"dias_acumulados": provision["dias_acumulados"], "monto_provisionado": provision["monto_provisionado"]},
    )


def test_diego_pierde_mas_dias_que_carla_en_el_mismo_rango(_escenario):
    # Comparativo, no depende de ESPERADOS -- corre siempre, incluso antes
    # de tener montos validados por el contador. Art. 208 CT: una ausencia
    # `injustificada` siempre descuenta vacaciones; `enfermedad_dentro_fondo`
    # nunca, así que con el mismo rango de fechas Diego debe terminar con
    # menos días acumulados que Carla.
    dias_carla = decimal.Decimal(str(_escenario["provision_carla"]["dias_acumulados"]))
    dias_diego = decimal.Decimal(str(_escenario["provision_diego"]["dias_acumulados"]))
    assert dias_diego < dias_carla


@pytest.mark.parametrize("clave", ["ana", "bruno", "carla", "diego"])
def test_decimo_cuatrimestre_dic_abr(_escenario, clave):
    mov = _escenario["decimo_por_empleado"][clave]
    actual = {
        "salario_bruto": mov["salario_bruto"],
        "css_empleado": mov["css_empleado"],
        "salario_neto": mov["salario_neto"],
    }
    _verificar(f"decimo.{clave}", ESPERADOS["decimo"][clave], actual)


def test_liquidacion_elena_despido_injustificado(_escenario):
    liquidacion = _escenario["liquidacion_elena"]
    actual = {campo: liquidacion[campo] for campo in ESPERADOS["liquidacion_elena"]}
    _verificar("liquidacion_elena", ESPERADOS["liquidacion_elena"], actual)

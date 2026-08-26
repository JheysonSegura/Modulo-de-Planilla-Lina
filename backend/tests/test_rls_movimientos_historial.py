import datetime
import decimal
import uuid

from sqlalchemy import select, text

from app.models import HistorialSalarial, MovimientoPlanilla
from tests.conftest import crear_empresa, crear_salario_minimo, crear_usuario, login_y_seleccionar, vincular

# Auditoría de seguridad 2026-08-25 (hallazgos M1/M2): hasta la migración
# 0036_rls_movimientos_historial, movimientos_planilla e historial_salarial
# eran las únicas tablas operativas sin RLS propio -- su aislamiento entre
# empresas dependía 100% de que el código de cada endpoint validara primero
# la planilla/contrato padre. Estos tests verifican la política de Postgres
# directamente (no solo el comportamiento del endpoint), para que un futuro
# db.get() sin RLS sobre estas tablas quede igual de protegido.

SALARIO = "900.00"


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa(db, client) -> dict:
    crear_salario_minimo(db, datetime.date(2020, 1, 1), decimal.Decimal("1.00"), fecha_fin=None)
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"user-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, "admin")
    return empresa, login_y_seleccionar(client, usuario, empresa)


def _crear_empleado_con_contrato(client, headers, fecha_inicio=datetime.date(2025, 1, 1)):
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
            "cargo": "Prueba RLS",
            "fecha_inicio": fecha_inicio.isoformat(),
            "salario_base": SALARIO,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return empleado_id, resp.json()["id"]


def _generar_planilla(client, headers, periodo_inicio, periodo_fin):
    resp = client.post(
        "/planillas/generar",
        json={
            "tipo": "mensual",
            "periodo_inicio": periodo_inicio.isoformat(),
            "periodo_fin": periodo_fin.isoformat(),
            "fecha_pago": periodo_fin.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _fijar_empresa_activa(db, empresa_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT set_config('app.empresa_actual', :eid, false)"), {"eid": str(empresa_id)}
    )


def test_historial_salarial_aisla_por_empresa_a_nivel_de_rls(db, client):
    empresa_a, headers_a = _preparar_empresa(db, client)
    _, contrato_a_id = _crear_empleado_con_contrato(client, headers_a)
    empresa_b, _headers_b = _preparar_empresa(db, client)

    stmt = select(HistorialSalarial).where(
        HistorialSalarial.contrato_id == uuid.UUID(contrato_a_id)
    )

    # Con la empresa B activa, Postgres no debe devolver la fila de la
    # empresa A -- aunque el query no filtre por empresa_id explícito,
    # es la política RLS la que lo hace.
    _fijar_empresa_activa(db, empresa_b.id)
    assert db.execute(stmt).scalars().all() == []

    # Con la empresa dueña activa, sí se ve.
    _fijar_empresa_activa(db, empresa_a.id)
    filas = db.execute(stmt).scalars().all()
    assert len(filas) == 1
    assert filas[0].empresa_id == empresa_a.id


def test_movimientos_planilla_aisla_por_empresa_a_nivel_de_rls(db, client):
    empresa_a, headers_a = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers_a)
    planilla_a = _generar_planilla(
        client, headers_a, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    empresa_b, _headers_b = _preparar_empresa(db, client)

    stmt = select(MovimientoPlanilla).where(
        MovimientoPlanilla.planilla_id == uuid.UUID(planilla_a["id"])
    )

    _fijar_empresa_activa(db, empresa_b.id)
    assert db.execute(stmt).scalars().all() == []

    _fijar_empresa_activa(db, empresa_a.id)
    filas = db.execute(stmt).scalars().all()
    assert len(filas) == 1
    assert filas[0].empresa_id == empresa_a.id


def test_recibo_de_pago_no_es_accesible_cruzando_planilla_de_otra_empresa(db, client):
    """Hallazgo M1: antes de validar la planilla primero, este endpoint
    solo comparaba movimiento.planilla_id contra el planilla_id de la URL
    -- dos valores que el propio atacante controla. Ahora, aunque alguien
    de la empresa B conociera los UUID reales de la planilla y el
    movimiento de la empresa A, la RLS (M2) + la validación explícita de
    la planilla (M1) lo bloquean con 404, no con una fuga de datos."""
    empresa_a, headers_a = _preparar_empresa(db, client)
    _crear_empleado_con_contrato(client, headers_a)
    planilla_a = _generar_planilla(
        client, headers_a, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31)
    )
    resp = client.get(f"/planillas/{planilla_a['id']}/movimientos", headers=headers_a)
    assert resp.status_code == 200
    movimiento_a_id = resp.json()[0]["id"]

    _empresa_b, headers_b = _preparar_empresa(db, client)
    resp = client.get(
        f"/planillas/{planilla_a['id']}/movimientos/{movimiento_a_id}/recibo",
        headers=headers_b,
    )
    assert resp.status_code == 404

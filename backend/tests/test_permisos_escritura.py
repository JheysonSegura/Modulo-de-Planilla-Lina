import uuid

from tests.conftest import crear_empresa, crear_usuario, login_y_seleccionar, vincular

# Todos los endpoints de escritura de negocio deben rechazar al rol
# 'consulta' con 403, sin importar si el recurso referenciado existe --
# require_escritura corre como dependency de FastAPI, antes de que el
# cuerpo del endpoint llegue a buscar nada en la base de datos, así que
# no hace falta armar empleados/contratos/planillas reales para probar
# esto: un UUID cualquiera en el path alcanza. Cada módulo ya tiene su
# propio archivo de tests que prueba el camino feliz (test_horas_extra,
# test_ausencias, test_vacaciones, test_liquidaciones, test_decimo,
# test_empleados_contratos, test_planillas*) con datos reales.


def _sufijo() -> str:
    return uuid.uuid4().hex[:8]


def _preparar_empresa_con_rol(db, client, rol: str) -> dict:
    empresa = crear_empresa(db, _sufijo())
    usuario = crear_usuario(db, f"{rol}-{_sufijo()}@example.com")
    vincular(db, usuario, empresa, rol)
    return login_y_seleccionar(client, usuario, empresa)


def _archivo_dummy():
    return {"archivo": ("archivo.pdf", b"%PDF-1.1 contenido de prueba", "application/pdf")}


def _endpoints_de_escritura() -> list[tuple[str, str, dict]]:
    eid = str(uuid.uuid4())  # empleado_id
    cid = str(uuid.uuid4())  # contrato_id
    aid = str(uuid.uuid4())  # ausencia_id
    rid = str(uuid.uuid4())  # registro_id (horas extra)
    kid = str(uuid.uuid4())  # concepto_id
    lid = str(uuid.uuid4())  # liquidacion_id
    pid = str(uuid.uuid4())  # planilla_id

    return [
        ("POST", "/empleados", {"json": {"identificacion": f"8-{_sufijo()}", "nombre_completo": "X"}}),
        ("PATCH", f"/empleados/{eid}", {"json": {}}),
        ("PUT", f"/empleados/{eid}/documento-identificacion", {"files": _archivo_dummy()}),
        ("PUT", f"/empleados/{eid}/documento-certificado-medico", {"files": _archivo_dummy()}),
        (
            "POST",
            f"/empleados/{eid}/contratos",
            {
                "json": {
                    "tipo_contrato": "indefinido",
                    "cargo": "Cargo",
                    "fecha_inicio": "2025-01-01",
                    "salario_base": "500.00",
                }
            },
        ),
        ("PATCH", f"/contratos/{cid}", {"json": {}}),
        (
            "POST",
            f"/contratos/{cid}/salario",
            {"json": {"salario_base": "600.00", "fecha_vigencia_desde": "2025-02-01"}},
        ),
        (
            "POST",
            f"/contratos/{cid}/horas-extra",
            {"json": {"fecha": "2025-03-03", "tipo_hora": "diurna", "horas": "1.0"}},
        ),
        ("DELETE", f"/contratos/{cid}/horas-extra/{rid}", {}),
        (
            "POST",
            f"/contratos/{cid}/ausencias",
            {"json": {"tipo": "injustificada", "fecha_desde": "2025-01-01", "fecha_hasta": "2025-01-02"}},
        ),
        ("PUT", f"/ausencias/{aid}/documento", {"files": _archivo_dummy()}),
        ("POST", f"/contratos/{cid}/vacaciones-tomadas", {"json": {"fecha": "2025-01-01", "dias": 1}}),
        ("POST", f"/contratos/{cid}/vacaciones-acumular", {"json": {"fecha_acuerdo": "2025-01-01"}}),
        (
            "POST",
            f"/contratos/{cid}/liquidacion",
            {"json": {"motivo": "renuncia_voluntaria", "fecha_terminacion": "2025-06-01"}},
        ),
        ("POST", f"/liquidaciones/{lid}/aprobar", {}),
        ("POST", f"/liquidaciones/{lid}/anular", {}),
        ("POST", f"/liquidaciones/{lid}/pagar", {"files": _archivo_dummy()}),
        (
            "POST",
            "/planillas/generar-decimo",
            {"json": {"cuatrimestre": "dic-abr", "anio": 2025, "fecha_pago": "2025-04-15"}},
        ),
        (
            "POST",
            f"/contratos/{cid}/conceptos-variables-pendientes",
            {"json": {"fecha": "2025-01-01", "tipo": "ingreso", "codigo": "bono", "monto": "50.00"}},
        ),
        ("DELETE", f"/contratos/{cid}/conceptos-variables-pendientes/{kid}", {}),
        (
            "POST",
            "/planillas/generar",
            {
                "json": {
                    "tipo": "quincenal",
                    "periodo_inicio": "2025-01-01",
                    "periodo_fin": "2025-01-15",
                    "fecha_pago": "2025-01-15",
                }
            },
        ),
        ("POST", f"/planillas/{pid}/aprobar", {}),
        ("POST", f"/planillas/{pid}/pagar", {"files": _archivo_dummy()}),
        ("PUT", f"/planillas/{pid}/constancia-pago", {"files": _archivo_dummy(), "data": {"motivo": "x"}}),
        ("POST", f"/planillas/{pid}/anular", {}),
    ]


def test_rol_consulta_no_puede_escribir_en_ningun_endpoint_de_negocio(client, db):
    headers = _preparar_empresa_con_rol(db, client, "consulta")

    for metodo, path, kwargs in _endpoints_de_escritura():
        resp = client.request(metodo, path, headers=headers, **kwargs)
        assert resp.status_code == 403, (
            f"{metodo} {path} debería rechazar al rol consulta con 403, "
            f"devolvió {resp.status_code}: {resp.text}"
        )


def test_rol_contador_si_puede_escribir(client, db):
    # Contador tiene acceso operativo completo: crear un empleado y
    # corregirlo después (PATCH) deben funcionar sin admin de por medio.
    headers = _preparar_empresa_con_rol(db, client, "contador")

    resp = client.post(
        "/empleados",
        json={"identificacion": f"8-{_sufijo()}", "nombre_completo": "Empleado de prueba"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    empleado_id = resp.json()["id"]

    resp = client.patch(
        f"/empleados/{empleado_id}",
        json={"telefono": "6000-0000", "codigo_pais": "+507"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["telefono"] == "6000-0000"

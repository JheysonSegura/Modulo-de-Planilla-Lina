import base64
import csv
import decimal
import io
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.models import AuditoriaCambio, Liquidacion, MovimientoPlanilla, Planilla, VacacionTomada
from app.repositories import contratos as contratos_repo
from app.repositories import empleados as empleados_repo
from app.repositories import empresas as empresas_repo
from app.repositories import horas_extra as horas_extra_repo
from app.repositories import movimientos_planilla as movimientos_planilla_repo
from app.repositories import usuarios as usuarios_repo

_CERO = decimal.Decimal("0")

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

COLUMNAS_RECIBO_PAGO = [
    ("empleado_nombre", "Empleado"),
    ("empleado_identificacion", "Identificación"),
    ("cargo", "Cargo"),
    ("periodo_inicio", "Período inicio"),
    ("periodo_fin", "Período fin"),
    ("salario_base_periodo", "Salario base"),
    ("total_horas_extra", "Horas extra"),
    ("total_otros_ingresos", "Otros ingresos"),
    ("salario_bruto", "Salario bruto"),
    ("css_empleado", "CSS empleado"),
    ("seguro_educativo_empleado", "Seguro educativo empleado"),
    ("isr_retenido", "ISR retenido"),
    ("otras_deducciones", "Otras deducciones"),
    ("salario_neto", "Salario neto"),
]

COLUMNAS_RECIBO_VACACION = [
    ("empleado_nombre", "Empleado"),
    ("empleado_identificacion", "Identificación"),
    ("fecha", "Fecha"),
    ("dias_tomados", "Días tomados"),
    ("valor_dia", "Valor día"),
    ("monto", "Monto"),
    ("saldo_despues", "Saldo después"),
]

COLUMNAS_RECIBO_LIQUIDACION = [
    ("empleado_nombre", "Empleado"),
    ("empleado_identificacion", "Identificación"),
    ("fecha_terminacion", "Fecha terminación"),
    ("motivo", "Motivo"),
    ("salario_pendiente", "Salario pendiente"),
    ("decimo_proporcional", "Décimo proporcional"),
    ("vacaciones_pendientes", "Vacaciones pendientes"),
    ("preaviso", "Preaviso"),
    ("indemnizacion", "Indemnización"),
    ("prima_antiguedad", "Prima de antigüedad"),
    ("salarios_caidos", "Salarios caídos"),
    ("otras_deducciones", "Otras deducciones"),
    ("penalidad_renuncia_sin_aviso", "Penalidad renuncia sin aviso"),
    ("monto_total", "Monto total"),
]

COLUMNAS_AUDITORIA = [
    ("fecha", "Fecha"),
    ("tabla_afectada", "Tabla afectada"),
    ("accion", "Acción"),
    ("empleado", "Empleado"),
    ("usuario", "Usuario"),
    ("registro_id", "ID del registro"),
    ("datos_anteriores", "Datos anteriores"),
    ("datos_nuevos", "Datos nuevos"),
]

COLUMNAS_EXPORTAR_PLANILLA = [
    ("empleado", "Empleado"),
    ("identificacion", "Identificación"),
    ("cargo", "Cargo"),
    ("salario_base", "Salario base"),
    ("salario_bruto", "Salario bruto"),
    ("css_empleado", "CSS empleado"),
    ("seguro_educativo_empleado", "Seguro educativo empleado"),
    ("isr_retenido", "ISR retenido"),
    ("otras_deducciones", "Otras deducciones"),
    ("salario_neto", "Salario neto"),
]


def armar_contexto_empresa(empresa) -> dict:
    logo_data_uri = None
    if empresa.logo:
        b64 = base64.b64encode(empresa.logo).decode("ascii")
        content_type = empresa.logo_content_type or "image/png"
        logo_data_uri = f"data:{content_type};base64,{b64}"
    return {
        "razon_social": empresa.razon_social,
        "nombre_comercial": empresa.nombre_comercial,
        "ruc": empresa.ruc,
        "dv": empresa.dv,
        "direccion": empresa.direccion,
        "telefono": empresa.telefono,
        "logo_data_uri": logo_data_uri,
    }


def armar_recibo_pago(db: Session, movimiento: MovimientoPlanilla) -> dict:
    """Junta lo que planilla_service ya calculó y guardó -- nunca
    recalcula nada, solo ensambla y valida que el desglose cuadre con
    lo persistido (campo `cuadra`, usado también en el test de este
    servicio)."""
    planilla = db.get(Planilla, movimiento.planilla_id)
    contrato = contratos_repo.get(db, movimiento.contrato_id)
    empresa = empresas_repo.get(db, planilla.empresa_id)

    registros_horas_extra = horas_extra_repo.listar_de_contrato(
        db, contrato.id, planilla.periodo_inicio, planilla.periodo_fin
    )
    por_tipo: dict[str, dict] = {}
    for registro in registros_horas_extra:
        acumulado = por_tipo.setdefault(
            registro.tipo_hora, {"tipo_hora": registro.tipo_hora, "horas": _CERO, "monto": _CERO}
        )
        acumulado["horas"] += registro.horas
        acumulado["monto"] += registro.monto_calculado
    horas_extra_por_tipo = sorted(por_tipo.values(), key=lambda d: d["tipo_hora"])
    total_horas_extra = sum((d["monto"] for d in horas_extra_por_tipo), _CERO)

    otros_ingresos = [
        c for c in movimiento.conceptos_variables if c.tipo == "ingreso" and c.codigo != "hora_extra"
    ]
    otras_deducciones_detalle = [c for c in movimiento.conceptos_variables if c.tipo == "deduccion"]
    total_otros_ingresos = sum((c.monto for c in otros_ingresos), _CERO)

    total_deducciones = (
        movimiento.css_empleado
        + movimiento.seguro_educativo_empleado
        + movimiento.isr_retenido
        + movimiento.otras_deducciones
    )
    bruto_recalculado = movimiento.salario_base_periodo + total_horas_extra + total_otros_ingresos

    return {
        "empresa": armar_contexto_empresa(empresa),
        "empleado_nombre": contrato.empleado.nombre_completo,
        "empleado_identificacion": contrato.empleado.identificacion,
        "cargo": contrato.cargo,
        "planilla_tipo": planilla.tipo,
        "periodo_inicio": planilla.periodo_inicio,
        "periodo_fin": planilla.periodo_fin,
        "fecha_pago": planilla.fecha_pago,
        "salario_base_periodo": movimiento.salario_base_periodo,
        "horas_extra_por_tipo": horas_extra_por_tipo,
        "total_horas_extra": total_horas_extra,
        "otros_ingresos": otros_ingresos,
        "total_otros_ingresos": total_otros_ingresos,
        "salario_bruto": movimiento.salario_bruto,
        "css_empleado": movimiento.css_empleado,
        "seguro_educativo_empleado": movimiento.seguro_educativo_empleado,
        "isr_retenido": movimiento.isr_retenido,
        "otras_deducciones_detalle": otras_deducciones_detalle,
        "otras_deducciones": movimiento.otras_deducciones,
        "total_deducciones": total_deducciones,
        "salario_neto": movimiento.salario_neto,
        "cuadra": (
            bruto_recalculado == movimiento.salario_bruto
            and (movimiento.salario_bruto - total_deducciones) == movimiento.salario_neto
        ),
    }


def armar_recibo_vacacion(db: Session, evento: VacacionTomada) -> dict:
    contrato = contratos_repo.get(db, evento.contrato_id)
    empresa = empresas_repo.get(db, evento.empresa_id)
    return {
        "empresa": armar_contexto_empresa(empresa),
        "empleado_nombre": contrato.empleado.nombre_completo,
        "empleado_identificacion": contrato.empleado.identificacion,
        "cargo": contrato.cargo,
        "fecha": evento.fecha,
        "dias_tomados": evento.dias_tomados,
        "valor_dia": evento.valor_dia,
        "monto": evento.monto,
        "dias_acumulados_snapshot": evento.dias_acumulados_snapshot,
        "dias_gozados_snapshot": evento.dias_gozados_snapshot,
        "saldo_despues": evento.dias_acumulados_snapshot - evento.dias_gozados_snapshot,
    }


def armar_recibo_liquidacion(db: Session, liquidacion: Liquidacion) -> dict:
    contrato = contratos_repo.get(db, liquidacion.contrato_id)
    empresa = empresas_repo.get(db, liquidacion.empresa_id)
    conceptos = [
        ("Salario pendiente", liquidacion.salario_pendiente),
        ("Décimo proporcional", liquidacion.decimo_proporcional),
        ("Vacaciones pendientes", liquidacion.vacaciones_pendientes),
        ("Preaviso", liquidacion.preaviso),
        ("Indemnización", liquidacion.indemnizacion),
        ("Prima de antigüedad", liquidacion.prima_antiguedad),
        ("Salarios caídos", liquidacion.salarios_caidos),
        ("Otras deducciones", -liquidacion.otras_deducciones),
        ("Penalidad renuncia sin aviso (Art. 222 CT)", -liquidacion.penalidad_renuncia_sin_aviso),
    ]
    return {
        "empresa": armar_contexto_empresa(empresa),
        "empleado_nombre": contrato.empleado.nombre_completo,
        "empleado_identificacion": contrato.empleado.identificacion,
        "cargo": contrato.cargo,
        "fecha_terminacion": liquidacion.fecha_terminacion,
        "motivo": liquidacion.motivo,
        "conceptos": conceptos,
        "referencia_sentencia": liquidacion.referencia_sentencia,
        "salario_pendiente": liquidacion.salario_pendiente,
        "decimo_proporcional": liquidacion.decimo_proporcional,
        "vacaciones_pendientes": liquidacion.vacaciones_pendientes,
        "preaviso": liquidacion.preaviso,
        "indemnizacion": liquidacion.indemnizacion,
        "prima_antiguedad": liquidacion.prima_antiguedad,
        "salarios_caidos": liquidacion.salarios_caidos,
        "otras_deducciones": liquidacion.otras_deducciones,
        "penalidad_renuncia_sin_aviso": liquidacion.penalidad_renuncia_sin_aviso,
        "monto_total": liquidacion.monto_total,
    }


def exportar_planilla(db: Session, planilla: Planilla) -> list[dict]:
    """Una fila por movimiento, para el export de la planilla completa
    (Excel/CSV) -- ver COLUMNAS_EXPORTAR_PLANILLA."""
    movimientos = movimientos_planilla_repo.listar_de_planilla(db, planilla.id)
    filas = []
    for movimiento in movimientos:
        contrato = contratos_repo.get(db, movimiento.contrato_id)
        filas.append(
            {
                "empleado": contrato.empleado.nombre_completo,
                "identificacion": contrato.empleado.identificacion,
                "cargo": contrato.cargo,
                "salario_base": movimiento.salario_base_periodo,
                "salario_bruto": movimiento.salario_bruto,
                "css_empleado": movimiento.css_empleado,
                "seguro_educativo_empleado": movimiento.seguro_educativo_empleado,
                "isr_retenido": movimiento.isr_retenido,
                "otras_deducciones": movimiento.otras_deducciones,
                "salario_neto": movimiento.salario_neto,
            }
        )
    return filas


def armar_reporte_planilla(db: Session, planilla: Planilla) -> dict:
    """Contexto para el PDF consolidado de la planilla completa (extensión
    Fase 16, 2026-08-07) -- reutiliza exportar_planilla, nunca duplica esa
    lógica de armado de filas."""
    filas = exportar_planilla(db, planilla)
    empresa = empresas_repo.get(db, planilla.empresa_id)
    total_neto = sum((fila["salario_neto"] for fila in filas), _CERO)
    elaborado_por = usuarios_repo.get_by_id(db, planilla.procesada_por) if planilla.procesada_por else None
    return {
        "empresa": armar_contexto_empresa(empresa),
        "planilla_tipo": planilla.tipo,
        "periodo_inicio": planilla.periodo_inicio,
        "periodo_fin": planilla.periodo_fin,
        "fecha_pago": planilla.fecha_pago,
        "filas": filas,
        "total_neto": total_neto,
        "elaborado_por": elaborado_por.nombre_completo if elaborado_por else None,
    }


def exportar_auditoria(db: Session, eventos: list[AuditoriaCambio]) -> list[dict]:
    """Una fila por evento, para el reporte de auditoría descargable
    (extensión Fase 16, 2026-08-07) -- ver COLUMNAS_AUDITORIA. Cachea
    empleado/usuario por id dentro de la misma llamada: un log de
    auditoría suele repetir el mismo empleado/usuario en muchas filas."""
    cache_empleados: dict = {}
    cache_usuarios: dict = {}

    def _nombre_empleado(empleado_id):
        if empleado_id is None:
            return None
        if empleado_id not in cache_empleados:
            empleado = empleados_repo.get(db, empleado_id)
            cache_empleados[empleado_id] = empleado.nombre_completo if empleado else str(empleado_id)
        return cache_empleados[empleado_id]

    def _email_usuario(usuario_id):
        if usuario_id is None:
            return None
        if usuario_id not in cache_usuarios:
            usuario = usuarios_repo.get_by_id(db, usuario_id)
            cache_usuarios[usuario_id] = usuario.email if usuario else str(usuario_id)
        return cache_usuarios[usuario_id]

    filas = []
    for evento in eventos:
        filas.append(
            {
                # openpyxl no acepta datetimes con tzinfo (created_at es
                # timestamptz) -- se formatea a texto, igual que el resto
                # de columnas de este export.
                "fecha": evento.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "tabla_afectada": evento.tabla_afectada,
                "accion": evento.accion,
                "empleado": _nombre_empleado(evento.empleado_id),
                "usuario": _email_usuario(evento.usuario_id),
                "registro_id": str(evento.registro_id),
                "datos_anteriores": json.dumps(evento.datos_anteriores, ensure_ascii=False)
                if evento.datos_anteriores
                else None,
                "datos_nuevos": json.dumps(evento.datos_nuevos, ensure_ascii=False)
                if evento.datos_nuevos
                else None,
            }
        )
    return filas


def render_pdf(template_name: str, contexto: dict) -> bytes:
    template = _env.get_template(template_name)
    html = template.render(**contexto)
    return HTML(string=html, base_url=str(_TEMPLATES_DIR)).write_pdf()


def render_excel(filas: list[dict], columnas: list[tuple[str, str]]) -> bytes:
    workbook = Workbook()
    hoja = workbook.active
    hoja.append([titulo for _, titulo in columnas])
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for fila in filas:
        hoja.append([fila.get(clave) for clave, _ in columnas])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_csv(filas: list[dict], columnas: list[tuple[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([titulo for _, titulo in columnas])
    for fila in filas:
        writer.writerow([fila.get(clave) for clave, _ in columnas])
    # utf-8-sig: para que Excel abra los acentos (RUC/dirección) sin
    # que el usuario tenga que elegir la codificación al importar.
    return buffer.getvalue().encode("utf-8-sig")

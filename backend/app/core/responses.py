from fastapi import Response

# Fase 16: primer punto del backend que devuelve binario en vez de JSON
# (recibos PDF/Excel, exportación de planilla CSV/Excel, logo de empresa).
_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}
_EXTENSIONES = {
    "pdf": "pdf",
    "excel": "xlsx",
    "csv": "csv",
}


def respuesta_archivo(contenido: bytes, formato: str, nombre_base: str) -> Response:
    """Arma una respuesta de descarga (Content-Disposition: attachment)
    para cualquier recibo/reporte generado por reportes_service, sea PDF,
    Excel o CSV. `nombre_base` va sin extensión (se agrega según formato)."""
    extension = _EXTENSIONES[formato]
    return Response(
        content=contenido,
        media_type=_MEDIA_TYPES[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre_base}.{extension}"'},
    )

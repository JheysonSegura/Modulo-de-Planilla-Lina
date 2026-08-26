import re

from fastapi import HTTPException, UploadFile, status

# Auditoría de seguridad 2026-08-25 (hallazgo A5): los endpoints de subida
# de archivos hacían `await archivo.read()` sin ningún límite de tamaño --
# un archivo arbitrariamente grande agota la memoria de un proceso que
# corre sin --workers (ver docker-compose.yml). Los topes son generosos
# para uso legítimo (documentos escaneados, plantillas Excel) pero acotan
# el peor caso.
MB = 1024 * 1024
LIMITE_LOGO = 5 * MB
LIMITE_DOCUMENTO = 10 * MB
LIMITE_EXCEL_MIGRACION = 20 * MB


async def leer_archivo_limitado(archivo: UploadFile, limite_bytes: int) -> bytes:
    """Lee el UploadFile completo, pero corta apenas se supera el límite
    -- nunca carga en memoria más de `limite_bytes + 1` bytes."""
    contenido = await archivo.read(limite_bytes + 1)
    if len(contenido) > limite_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El archivo excede el tamaño máximo permitido ({limite_bytes // MB} MB).",
        )
    return contenido


# Auditoría de seguridad 2026-08-25 (hallazgo M4): el `content_type` de un
# UploadFile lo declara el cliente, no algo que el servidor verifique --
# spoofeable con cualquier herramienta HTTP. Estas validaciones miran los
# bytes reales del archivo (magic bytes / heurística de contenido), como
# defensa adicional a la validación de `content_type` que ya hacía cada
# router.
_FIRMAS_IMAGEN: dict[str, bytes] = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}
_PATRON_SVG_PELIGROSO = re.compile(rb"<script|on\w+\s*=|javascript:", re.IGNORECASE)


def validar_firma_imagen(contenido: bytes, content_type: str) -> None:
    """Confirma que el contenido real coincida con el `content_type`
    declarado. Para SVG (el único formato de texto en
    `_TIPOS_LOGO_PERMITIDOS`, no tiene magic bytes binarios) se rechaza si
    contiene `<script>`/manejadores `on*=`/`javascript:` -- no es un
    sanitizador completo de SVG, pero cierra el vector de XSS obvio en un
    archivo que hoy no se sirve inline como HTML (se consume como blob en
    un `<img>`, ver CLAUDE.md), sin bloquear SVGs legítimos de logo."""
    if content_type == "image/svg+xml":
        if _PATRON_SVG_PELIGROSO.search(contenido):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El SVG contiene contenido no permitido (scripts o manejadores de eventos).",
            )
        return
    if content_type == "image/webp":
        if contenido[:4] != b"RIFF" or contenido[8:12] != b"WEBP":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El contenido del archivo no coincide con el formato WEBP declarado.",
            )
        return
    firma = _FIRMAS_IMAGEN.get(content_type)
    if firma is not None and not contenido.startswith(firma):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El contenido del archivo no coincide con el formato {content_type} declarado.",
        )


def validar_firma_excel(contenido: bytes) -> None:
    """Un .xlsx es un ZIP -- todo ZIP empieza con la firma 'PK\\x03\\x04'."""
    if not contenido.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "El archivo no es un Excel (.xlsx) válido.",
        )

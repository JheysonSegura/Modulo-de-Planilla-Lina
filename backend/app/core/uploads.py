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

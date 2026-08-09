/**
 * El backend (FastAPI) manda el motivo real de un rechazo en el body
 * como `{"detail": ...}` -- un string en los HTTPException de negocio
 * (ej. "El salario está por debajo del mínimo...") o una lista de
 * errores de validación de Pydantic (`[{msg, loc, type}, ...]`) cuando
 * el body ni siquiera pasa el schema. ofetch (useApi.ts/useEmpleados.ts/
 * etc.) adjunta ese body parseado en `error.data`. Sin este helper, los
 * catch de los formularios mostraban `String(error)`, que es solo
 * "FetchError: [POST] ".../ruta": 422 Unprocessable Entity" -- nunca el
 * motivo real.
 */
export function extraerMensajeError(error: unknown): string {
  const detail = (error as { data?: { detail?: unknown } })?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const mensajes = detail
      .map(item => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null))
      .filter((m): m is string => !!m)
    if (mensajes.length > 0) return mensajes.join(' | ')
  }

  return String(error)
}

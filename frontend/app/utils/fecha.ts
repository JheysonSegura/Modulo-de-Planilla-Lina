/**
 * Formatea una fecha PURA (YYYY-MM-DD, sin hora -- salarios, períodos,
 * fechas de contrato, etc.) para mostrar. `new Date('2025-01-01')` la
 * interpreta como medianoche UTC; sin fijar `timeZone: 'UTC'` aquí,
 * `toLocaleDateString` la vuelve a convertir a la zona horaria local
 * del navegador y en cualquier zona detrás de UTC (como Panamá,
 * UTC-5) el día se corre uno hacia atrás (31/12/2024 en vez de
 * 01/01/2025). Para timestamps reales con hora (ej. auditoría), usar
 * `toLocaleString` normal -- esos sí deben convertirse a hora local.
 */
export function formatearFecha(fecha: string | null | undefined, fallback = '—'): string {
  if (!fecha) return fallback
  return new Date(fecha).toLocaleDateString('es-PA', { timeZone: 'UTC' })
}

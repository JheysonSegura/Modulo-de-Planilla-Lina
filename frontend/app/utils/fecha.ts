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

const EDAD_MINIMA_ANOS = 18

/**
 * Panamá: mayoría de edad a los 18 años. `fechaIso` es una fecha pura
 * (YYYY-MM-DD) -- se compara por partes de calendario, no con objetos
 * Date con hora, por el mismo motivo de zona horaria que formatearFecha.
 */
export function esMayorDeEdad(fechaIso: string): boolean {
  const [anoStr, mesStr, diaStr] = fechaIso.split('-')
  const ano = Number(anoStr)
  const mes = Number(mesStr)
  const dia = Number(diaStr)
  if (!ano || !mes || !dia) return true // fecha incompleta: no es este validador el que debe rechazarla

  const hoy = new Date()
  let edad = hoy.getFullYear() - ano
  const aunNoCumpleEsteAno = hoy.getMonth() + 1 < mes || (hoy.getMonth() + 1 === mes && hoy.getDate() < dia)
  if (aunNoCumpleEsteAno) edad -= 1

  return edad >= EDAD_MINIMA_ANOS
}

/** Fecha máxima seleccionable para que la persona ya sea mayor de edad hoy (YYYY-MM-DD). */
export function fechaMaximaMayorDeEdad(): string {
  const hoy = new Date()
  const fecha = new Date(hoy.getFullYear() - EDAD_MINIMA_ANOS, hoy.getMonth(), hoy.getDate())
  return fecha.toISOString().slice(0, 10)
}

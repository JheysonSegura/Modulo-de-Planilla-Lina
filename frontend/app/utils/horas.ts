export function combinarHorasYMinutos(horas: number, minutos: number): number {
  return Math.round((horas + minutos / 60) * 100) / 100
}

export function formatearHorasDecimal(valorDecimal: string | number): string {
  const decimal = Number(valorDecimal)
  const horas = Math.trunc(decimal)
  const minutos = Math.round((decimal - horas) * 60)
  return `${horas}h ${minutos.toString().padStart(2, '0')}m`
}

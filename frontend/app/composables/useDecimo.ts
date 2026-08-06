export interface ProvisionDecimo {
  id: string
  contrato_id: string
  cuatrimestre: 'dic-abr' | 'abr-ago' | 'ago-dic'
  anio: number
  monto_acumulado: string
  fecha_pago_programada: string
  pagado: boolean
  fecha_pago_real: string | null
  movimiento_planilla_id: string | null
}

export function useDecimo() {
  const api = useApi()

  return {
    provisiones: (contratoId: string) => api.get<ProvisionDecimo[]>(`/contratos/${contratoId}/provisiones-decimo`),
    generarPago: (body: Record<string, unknown>) => api.post('/planillas/generar-decimo', body)
  }
}

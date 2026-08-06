export interface ProvisionVacaciones {
  id: string
  contrato_id: string
  fecha_inicio_periodo: string
  dias_acumulados: string
  dias_gozados: string
  monto_provisionado: string
  estado: 'abierto' | 'acumulado' | 'liquidado'
  notificado_autoridad_trabajo: boolean
  saldo_disponible: string
}

export function useVacaciones() {
  const api = useApi()

  return {
    provisiones: (contratoId: string) => api.get<ProvisionVacaciones[]>(`/contratos/${contratoId}/provisiones-vacaciones`),
    tomar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<ProvisionVacaciones>(`/contratos/${contratoId}/vacaciones-tomadas`, body),
    acumular: (contratoId: string, body: Record<string, unknown>) =>
      api.post<ProvisionVacaciones>(`/contratos/${contratoId}/vacaciones-acumular`, body)
  }
}

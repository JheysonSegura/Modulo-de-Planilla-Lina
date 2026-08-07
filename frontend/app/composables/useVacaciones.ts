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

// Fase 16: historial por evento de "tomar vacaciones" -- una fila por
// período efectivamente tocado (una toma puede generar 2 filas si
// cruza el período 'acumulado' y el 'abierto').
export interface VacacionTomada {
  id: string
  provision_id: string
  contrato_id: string
  fecha: string
  dias_tomados: string
  valor_dia: string
  monto: string
  created_at: string
}

export function useVacaciones() {
  const api = useApi()

  return {
    provisiones: (contratoId: string) => api.get<ProvisionVacaciones[]>(`/contratos/${contratoId}/provisiones-vacaciones`),
    tomar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<ProvisionVacaciones>(`/contratos/${contratoId}/vacaciones-tomadas`, body),
    acumular: (contratoId: string, body: Record<string, unknown>) =>
      api.post<ProvisionVacaciones>(`/contratos/${contratoId}/vacaciones-acumular`, body),
    tomadas: (contratoId: string) => api.get<VacacionTomada[]>(`/contratos/${contratoId}/vacaciones-tomadas`)
  }
}

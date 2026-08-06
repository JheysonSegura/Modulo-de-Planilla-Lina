export interface Planilla {
  id: string
  tipo: string
  periodo_inicio: string
  periodo_fin: string
  fecha_pago: string
  estado: 'borrador' | 'procesada' | 'pagada' | 'anulada'
}

export interface MovimientoPlanilla {
  id: string
  contrato_id: string
  salario_base_periodo: string
  salario_bruto: string
  css_empleado: string
  css_patronal: string
  seguro_educativo_empleado: string
  seguro_educativo_patronal: string
  riesgo_profesional_patronal: string
  isr_retenido: string
  otras_deducciones: string
  salario_neto: string
  conceptos_variables: { id: string, tipo: string, codigo: string, descripcion: string | null, monto: string }[]
}

export function usePlanillas() {
  const api = useApi()

  return {
    listar: (tipo?: string, estado?: string) => api.get<Planilla[]>('/planillas', { tipo, estado }),
    obtener: (id: string) => api.get<Planilla>(`/planillas/${id}`),
    generar: (body: Record<string, unknown>) => api.post<Planilla>('/planillas/generar', body),
    aprobar: (id: string) => api.post<Planilla>(`/planillas/${id}/aprobar`),
    movimientos: (id: string) => api.get<MovimientoPlanilla[]>(`/planillas/${id}/movimientos`)
  }
}

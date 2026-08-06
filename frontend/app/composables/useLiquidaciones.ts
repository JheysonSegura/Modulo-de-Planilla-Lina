export type MotivoTerminacion
  = | 'renuncia_voluntaria'
    | 'renuncia_justificada'
    | 'despido_justificado'
    | 'despido_causa_economica'
    | 'despido_injustificado'
    | 'mutuo_acuerdo'

export interface Liquidacion {
  id: string
  contrato_id: string
  fecha_terminacion: string
  motivo: MotivoTerminacion
  salario_pendiente: string
  decimo_proporcional: string
  vacaciones_pendientes: string
  prima_antiguedad: string
  indemnizacion: string
  preaviso: string
  otras_deducciones: string
  salarios_caidos: string
  referencia_sentencia: string | null
  penalidad_renuncia_sin_aviso: string
  monto_total: string
  estado: 'borrador' | 'aprobada' | 'pagada'
}

export function useLiquidaciones() {
  const api = useApi()

  return {
    listarDeContrato: (contratoId: string) => api.get<Liquidacion[]>(`/contratos/${contratoId}/liquidaciones`),
    generar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<Liquidacion>(`/contratos/${contratoId}/liquidacion`, body),
    pagar: (liquidacionId: string) => api.post<Liquidacion>(`/liquidaciones/${liquidacionId}/pagar`)
  }
}

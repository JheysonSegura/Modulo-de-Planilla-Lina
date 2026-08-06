export type TipoAusencia
  = | 'enfermedad_dentro_fondo'
    | 'enfermedad_excede_fondo'
    | 'embarazo'
    | 'riesgo_profesional'
    | 'huelga_legal'
    | 'licencia_sindical_o_estado'
    | 'licencia_autorizada_empleador'
    | 'arresto_o_prision_preventiva'
    | 'injustificada'

export interface Ausencia {
  id: string
  contrato_id: string
  tipo: TipoAusencia
  fecha_desde: string
  fecha_hasta: string
  certificado_ref: string | null
}

export function useAusencias() {
  const api = useApi()

  return {
    listar: (contratoId: string) => api.get<Ausencia[]>(`/contratos/${contratoId}/ausencias`),
    registrar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<Ausencia>(`/contratos/${contratoId}/ausencias`, body)
  }
}

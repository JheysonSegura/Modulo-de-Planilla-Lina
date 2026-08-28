export interface RegistroHorasExtra {
  id: string
  contrato_id: string
  fecha: string
  tipo_hora: 'diurna' | 'nocturna' | 'prolongacion_nocturna'
  tipo_dia: 'ordinario' | 'domingo_descanso' | 'feriado_duelo_nacional'
  horas: string
  observaciones: string | null
  horas_dentro_limite: string
  horas_exceso_limite: string
  valor_hora_ordinaria: string
  factor_tipo_hora: string
  factor_tipo_dia: string
  factor_exceso_limite: string
  monto_dentro_limite: string
  monto_exceso_limite: string
  monto_calculado: string
  aplicado: boolean
}

export function useHorasExtra() {
  const api = useApi()

  return {
    listar: (contratoId: string, desde?: string, hasta?: string) =>
      api.get<RegistroHorasExtra[]>(`/contratos/${contratoId}/horas-extra`, { desde, hasta }),
    registrar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<RegistroHorasExtra>(`/contratos/${contratoId}/horas-extra`, body),
    eliminar: (contratoId: string, registroId: string) =>
      api.del(`/contratos/${contratoId}/horas-extra/${registroId}`)
  }
}

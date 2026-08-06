export interface ConceptoVariablePendiente {
  id: string
  contrato_id: string
  fecha: string
  tipo: 'ingreso' | 'deduccion'
  codigo: string
  descripcion: string | null
  monto: string
  aplicado: boolean
  movimiento_planilla_id: string | null
}

export function useConceptosVariables() {
  const api = useApi()

  return {
    listar: (contratoId: string, desde?: string, hasta?: string) =>
      api.get<ConceptoVariablePendiente[]>(`/contratos/${contratoId}/conceptos-variables-pendientes`, { desde, hasta }),
    registrar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<ConceptoVariablePendiente>(`/contratos/${contratoId}/conceptos-variables-pendientes`, body),
    eliminar: (contratoId: string, conceptoId: string) =>
      api.del(`/contratos/${contratoId}/conceptos-variables-pendientes/${conceptoId}`)
  }
}

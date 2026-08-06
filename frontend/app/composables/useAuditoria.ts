export interface AuditoriaCambio {
  id: string
  tabla_afectada: string
  registro_id: string
  empleado_id: string | null
  usuario_id: string | null
  accion: string
  datos_anteriores: Record<string, unknown> | null
  datos_nuevos: Record<string, unknown> | null
  created_at: string
}

export function useAuditoria() {
  const api = useApi()

  return {
    listar: (empleadoId?: string, tablaAfectada?: string, accion?: string) =>
      api.get<AuditoriaCambio[]>('/auditoria', {
        empleado_id: empleadoId,
        tabla_afectada: tablaAfectada,
        accion
      })
  }
}

export interface Empresa {
  id: string
  razon_social: string
  nombre_comercial: string | null
  ruc: string
  clase_riesgo: string | null
  region: string | null
  actividad_economica: string | null
  tamano_empresa: string | null
}

export function useEmpresa() {
  const api = useApi()

  return {
    obtenerActual: () => api.get<Empresa>('/empresas/actual'),
    actualizarActual: (body: Record<string, unknown>) => api.patch<Empresa>('/empresas/actual', body)
  }
}

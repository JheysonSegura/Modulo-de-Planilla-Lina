export interface Empresa {
  id: string
  razon_social: string
  nombre_comercial: string | null
  ruc: string
  dv: string | null
  direccion: string | null
  telefono: string | null
  clase_riesgo: string | null
  region: string | null
  actividad_economica: string | null
  tamano_empresa: string | null
  tiene_logo: boolean
}

export function useEmpresa() {
  const api = useApi()

  return {
    obtenerActual: () => api.get<Empresa>('/empresas/actual'),
    actualizarActual: (body: Record<string, unknown>) => api.patch<Empresa>('/empresas/actual', body)
  }
}

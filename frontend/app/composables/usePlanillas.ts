export interface Planilla {
  id: string
  tipo: string
  periodo_inicio: string
  periodo_fin: string
  fecha_pago: string
  estado: 'borrador' | 'procesada' | 'pagada' | 'anulada'
  tiene_constancia_pago: boolean
  documento_constancia_pago_nombre_archivo: string | null
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
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  // Mismo patrón de blob + FormData que useAusencias.ts: useApi.ts no
  // soporta binarios, así que este helper vive duplicado acá en vez
  // de generalizarse.
  async function pedirBlob(path: string): Promise<Blob> {
    const intentar = () =>
      $fetch<Blob>(path, {
        baseURL: config.public.apiBase,
        method: 'GET',
        responseType: 'blob',
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })

    try {
      return await intentar()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) return await intentar()
        await navigateTo('/login')
      }
      throw error
    }
  }

  async function subirArchivo(path: string, archivo: File): Promise<Planilla> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch<Planilla>(path, {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: formData,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })

    try {
      return await intentar()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) return await intentar()
        await navigateTo('/login')
      }
      throw error
    }
  }

  async function reemplazarConstancia(id: string, archivo: File, motivo: string): Promise<Planilla> {
    const formData = new FormData()
    formData.append('archivo', archivo)
    formData.append('motivo', motivo)

    const intentar = () =>
      $fetch<Planilla>(`/planillas/${id}/constancia-pago`, {
        baseURL: config.public.apiBase,
        method: 'PUT',
        body: formData,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })

    try {
      return await intentar()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) return await intentar()
        await navigateTo('/login')
      }
      throw error
    }
  }

  return {
    listar: (tipo?: string, estado?: string) => api.get<Planilla[]>('/planillas', { tipo, estado }),
    obtener: (id: string) => api.get<Planilla>(`/planillas/${id}`),
    generar: (body: Record<string, unknown>) => api.post<Planilla>('/planillas/generar', body),
    aprobar: (id: string) => api.post<Planilla>(`/planillas/${id}/aprobar`),
    anular: (id: string) => api.post<Planilla>(`/planillas/${id}/anular`),
    pagar: (id: string, archivo: File) => subirArchivo(`/planillas/${id}/pagar`, archivo),
    reemplazarConstancia,
    obtenerConstanciaPagoUrl: async (id: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/planillas/${id}/constancia-pago`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    },
    movimientos: (id: string) => api.get<MovimientoPlanilla[]>(`/planillas/${id}/movimientos`)
  }
}

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
  estado: 'borrador' | 'aprobada' | 'anulada' | 'pagada'
  tiene_constancia_pago: boolean
  documento_constancia_pago_nombre_archivo: string | null
}

export function useLiquidaciones() {
  const api = useApi()
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  // Mismo patrón de blob + FormData que usePlanillas.ts: useApi.ts no
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

  async function pagar(liquidacionId: string, archivo: File): Promise<Liquidacion> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch<Liquidacion>(`/liquidaciones/${liquidacionId}/pagar`, {
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

  return {
    listarDeContrato: (contratoId: string) => api.get<Liquidacion[]>(`/contratos/${contratoId}/liquidaciones`),
    generar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<Liquidacion>(`/contratos/${contratoId}/liquidacion`, body),
    aprobar: (liquidacionId: string) => api.post<Liquidacion>(`/liquidaciones/${liquidacionId}/aprobar`),
    anular: (liquidacionId: string) => api.post<Liquidacion>(`/liquidaciones/${liquidacionId}/anular`),
    pagar,
    obtenerConstanciaPagoUrl: async (liquidacionId: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/liquidaciones/${liquidacionId}/constancia-pago`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    }
  }
}

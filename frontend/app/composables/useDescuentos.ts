export type TipoDescuento
  = | 'prestamo_empresa'
    | 'prestamo_bancario'
    | 'hipoteca'
    | 'cooperativa'
    | 'pension_alimenticia'
    | 'embargo'

export type FrecuenciaDescuento = 'mensual' | 'quincenal'

export interface Descuento {
  id: string
  contrato_id: string
  tipo: TipoDescuento
  acreedor: string
  referencia: string | null
  monto_total: string | null
  plazo_meses: number | null
  frecuencia: FrecuenciaDescuento
  numero_cuotas: number | null
  cuota: string
  fecha_inicio: string
  estado: 'activo' | 'cerrado'
  fecha_cierre: string | null
  motivo_cierre: string | null
  observacion: string | null
  created_at: string
  total_cobrado: string
  saldo: string | null
  cuotas_cobradas: number
  estado_actual: 'activo' | 'pagado' | 'cerrado' | 'terminado'
  tiene_documento: boolean
  documento_nombre_archivo: string | null
}

export interface SimulacionDescuento {
  numero_cuotas: number
  cuota: string
  ultima_cuota: string
  fecha_primera_cuota: string
  fecha_ultima_cuota: string
}

export interface CuotaDescuento {
  id: string
  fecha_cobro: string
  monto: string
  monto_programado: string
  origen: 'quincenal' | 'mensual' | 'vacaciones' | 'liquidacion'
  planilla_id: string | null
  liquidacion_id: string | null
  anulada: boolean
}

export const ETIQUETAS_TIPO_DESCUENTO: Record<TipoDescuento, string> = {
  prestamo_empresa: 'Préstamo de la empresa',
  prestamo_bancario: 'Préstamo bancario / financiera',
  hipoteca: 'Hipoteca / vivienda',
  cooperativa: 'Cooperativa / ahorro',
  pension_alimenticia: 'Pensión alimenticia',
  embargo: 'Embargo'
}

export function useDescuentos() {
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

  async function subirArchivo(path: string, archivo: File): Promise<Descuento> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch<Descuento>(path, {
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
    listar: (contratoId: string) => api.get<Descuento[]>(`/contratos/${contratoId}/descuentos`),
    simular: (contratoId: string, body: Record<string, unknown>) =>
      api.post<SimulacionDescuento>(`/contratos/${contratoId}/descuentos/simular`, body),
    registrar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<Descuento>(`/contratos/${contratoId}/descuentos`, body),
    listarCuotas: (descuentoId: string) => api.get<CuotaDescuento[]>(`/descuentos/${descuentoId}/cuotas`),
    cerrar: (descuentoId: string, motivo: string) =>
      api.post<Descuento>(`/descuentos/${descuentoId}/cerrar`, { motivo }),
    eliminar: (descuentoId: string) => api.del(`/descuentos/${descuentoId}`),
    obtenerDocumentoUrl: async (descuentoId: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/descuentos/${descuentoId}/documento`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    },
    subirDocumento: (descuentoId: string, archivo: File) =>
      subirArchivo(`/descuentos/${descuentoId}/documento`, archivo)
  }
}

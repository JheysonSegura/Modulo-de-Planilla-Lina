export interface MigracionDisponible {
  disponible: boolean
  motivo?: string | null
}

export interface ErrorValidacionMigracion {
  hoja: string
  fila: number
  campo?: string | null
  mensaje: string
}

export interface ResumenMigracion {
  empleados: number
  contratos: number
  tramos_salario_adicionales: number
  dias_vacaciones_acumulados_totales: string
  isr_total_a_cargar: string
  meses_bruto_historico_cargados: number
}

export interface ResultadoValidacionMigracion {
  errores: ErrorValidacionMigracion[]
  resumen: ResumenMigracion | null
}

export interface ResultadoMigracionOut {
  resumen: ResumenMigracion
  fecha_corte: string
}

/**
 * Asistente de migración de datos históricos (empresa que viene de otro
 * sistema) -- mismo patrón de $fetch directo + reintento tras 401 que
 * useReportes.ts (blob) y usePlanillas.subirArchivo (multipart), porque
 * useApi.ts no soporta binarios ni blobs.
 */
export function useMigracionDatos() {
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  async function conReintento<T>(hacer: () => Promise<T>): Promise<T> {
    try {
      return await hacer()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) return await hacer()
        await navigateTo('/login')
      }
      throw error
    }
  }

  function disponible(): Promise<MigracionDisponible> {
    return conReintento(() =>
      $fetch<MigracionDisponible>('/empresas/actual/migracion/disponible', {
        baseURL: config.public.apiBase,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })
    )
  }

  async function descargarPlantilla(): Promise<void> {
    const blob = await conReintento(() =>
      $fetch<Blob>('/empresas/actual/migracion/plantilla', {
        baseURL: config.public.apiBase,
        responseType: 'blob',
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })
    )
    const url = URL.createObjectURL(blob)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = 'plantilla-migracion-datos.xlsx'
    document.body.appendChild(enlace)
    enlace.click()
    enlace.remove()
    URL.revokeObjectURL(url)
  }

  function _armarFormData(archivo: File, fechaCorte: string): FormData {
    const formData = new FormData()
    formData.append('archivo', archivo)
    formData.append('fecha_corte', fechaCorte)
    return formData
  }

  function validar(archivo: File, fechaCorte: string): Promise<ResultadoValidacionMigracion> {
    return conReintento(() =>
      $fetch<ResultadoValidacionMigracion>('/empresas/actual/migracion/validar', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: _armarFormData(archivo, fechaCorte),
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })
    )
  }

  function confirmar(archivo: File, fechaCorte: string): Promise<ResultadoMigracionOut> {
    return conReintento(() =>
      $fetch<ResultadoMigracionOut>('/empresas/actual/migracion/confirmar', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: _armarFormData(archivo, fechaCorte),
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })
    )
  }

  return { disponible, descargarPlantilla, validar, confirmar }
}

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
  tiene_documento_constancia: boolean
  documento_constancia_nombre_archivo: string | null
}

export function useAusencias() {
  const api = useApi()
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  // Mismo patrón de blob + FormData que useEmpleados.ts (documentos de
  // empleado): useApi.ts no soporta binarios, así que este helper vive
  // duplicado acá en vez de generalizarse.
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

  async function subirArchivo(path: string, archivo: File): Promise<Ausencia> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch<Ausencia>(path, {
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
    listar: (contratoId: string) => api.get<Ausencia[]>(`/contratos/${contratoId}/ausencias`),
    registrar: (contratoId: string, body: Record<string, unknown>) =>
      api.post<Ausencia>(`/contratos/${contratoId}/ausencias`, body),
    obtenerDocumentoUrl: async (ausenciaId: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/ausencias/${ausenciaId}/documento`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    },
    subirDocumento: (ausenciaId: string, archivo: File) =>
      subirArchivo(`/ausencias/${ausenciaId}/documento`, archivo)
  }
}

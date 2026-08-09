// Subconjunto de campos que expone el formulario compartido
// FormDatosPersonales.vue (alta y edición). Los campos de identidad legal
// (identificacion, nombre_completo, email_personal) quedan fuera: solo se
// piden en el alta, nunca son editables después.
export interface DatosPersonalesForm {
  fecha_nacimiento?: string
  sexo?: 'masculino' | 'femenino' | 'otro'
  nacionalidad?: string
  codigo_pais?: string
  telefono?: string
  direccion?: string
  padece_enfermedad?: boolean
  detalle_enfermedad?: string
}

export interface Empleado {
  id: string
  tipo_identificacion: 'cedula' | 'pasaporte'
  identificacion: string
  nombre_completo: string
  fecha_nacimiento: string | null
  nacionalidad: string | null
  sexo: 'masculino' | 'femenino' | 'otro' | null
  email_personal: string | null
  codigo_pais: string | null
  telefono: string | null
  direccion: string | null
  numero_seguro_social: string | null
  padece_enfermedad: boolean
  detalle_enfermedad: string | null
  tiene_documento_identificacion: boolean
  documento_identificacion_nombre_archivo: string | null
  tiene_documento_certificado_medico: boolean
  documento_certificado_medico_nombre_archivo: string | null
  estado: 'activo' | 'inactivo'
  created_at: string
  updated_at: string
}

export function useEmpleados() {
  const api = useApi()
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  // Mismo patrón de blob + FormData que useReportes.ts (logo de empresa):
  // useApi.ts no soporta binarios, así que este helper vive duplicado acá
  // en vez de generalizarse, igual que ya pasó con useReportes.
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

  async function subirArchivo(path: string, archivo: File): Promise<Empleado> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch<Empleado>(path, {
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
    listar: () => api.get<Empleado[]>('/empleados'),
    obtener: (id: string) => api.get<Empleado>(`/empleados/${id}`),
    crear: (body: Record<string, unknown>) => api.post<Empleado>('/empleados', body),
    actualizar: (id: string, body: Record<string, unknown>) => api.patch<Empleado>(`/empleados/${id}`, body),
    obtenerDocumentoIdentificacionUrl: async (id: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/empleados/${id}/documento-identificacion`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    },
    subirDocumentoIdentificacion: (id: string, archivo: File) =>
      subirArchivo(`/empleados/${id}/documento-identificacion`, archivo),
    obtenerDocumentoCertificadoMedicoUrl: async (id: string): Promise<string | null> => {
      try {
        const blob = await pedirBlob(`/empleados/${id}/documento-certificado-medico`)
        return URL.createObjectURL(blob)
      } catch {
        return null
      }
    },
    subirDocumentoCertificadoMedico: (id: string, archivo: File) =>
      subirArchivo(`/empleados/${id}/documento-certificado-medico`, archivo)
  }
}

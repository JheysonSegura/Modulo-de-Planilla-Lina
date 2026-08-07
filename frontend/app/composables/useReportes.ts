/**
 * Fase 16: descarga de boletas/reportes (PDF/Excel/CSV) y logo de
 * empresa. Primer composable del repo que maneja binarios -- mismo
 * patrón de token + reintento tras 401 que useApi.ts, pero con
 * responseType 'blob' en vez de JSON.
 */
export function useReportes() {
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  async function pedirBlob(path: string, params?: Record<string, unknown>): Promise<Blob> {
    const intentar = () =>
      $fetch<Blob>(path, {
        baseURL: config.public.apiBase,
        method: 'GET',
        query: params,
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

  async function descargar(path: string, params: Record<string, unknown> | undefined, nombreArchivo: string) {
    const blob = await pedirBlob(path, params)
    const url = URL.createObjectURL(blob)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = nombreArchivo
    document.body.appendChild(enlace)
    enlace.click()
    enlace.remove()
    URL.revokeObjectURL(url)
  }

  async function obtenerLogoUrl(): Promise<string | null> {
    try {
      const blob = await pedirBlob('/empresas/actual/logo')
      return URL.createObjectURL(blob)
    } catch {
      return null
    }
  }

  async function subirLogo(archivo: File): Promise<void> {
    const formData = new FormData()
    formData.append('archivo', archivo)

    const intentar = () =>
      $fetch('/empresas/actual/logo', {
        baseURL: config.public.apiBase,
        method: 'PUT',
        body: formData,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })

    try {
      await intentar()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) {
          await intentar()
          return
        }
        await navigateTo('/login')
      }
      throw error
    }
  }

  return { descargar, obtenerLogoUrl, subirLogo }
}

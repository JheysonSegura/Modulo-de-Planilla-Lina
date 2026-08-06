interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: Record<string, unknown>
  params?: Record<string, unknown>
}

/**
 * Cliente HTTP genérico para el resto de la app (todo lo que no sea
 * el propio flujo de /auth, que vive en useAuth). Agrega el access
 * token vigente y, ante un 401, intenta refrescar la sesión UNA vez
 * y reintenta la misma request antes de rendirse.
 */
export function useApi() {
  const config = useRuntimeConfig()
  const { accessToken, refrescarSesion } = useAuth()

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const intentar = () =>
      $fetch<T>(path, {
        baseURL: config.public.apiBase,
        method: options.method ?? 'GET',
        body: options.body,
        query: options.params,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })

    try {
      return await intentar()
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        const refrescado = await refrescarSesion()
        if (refrescado) {
          return await intentar()
        }
        await navigateTo('/login')
      }
      throw error
    }
  }

  return {
    get: <T>(path: string, params?: Record<string, unknown>) => request<T>(path, { method: 'GET', params }),
    post: <T>(path: string, body?: Record<string, unknown>) => request<T>(path, { method: 'POST', body }),
    patch: <T>(path: string, body?: Record<string, unknown>) => request<T>(path, { method: 'PATCH', body }),
    del: <T>(path: string) => request<T>(path, { method: 'DELETE' })
  }
}

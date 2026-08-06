export interface Usuario {
  id: string
  email: string
  nombre_completo: string
}

export interface EmpresaAcceso {
  empresa_id: string
  razon_social: string
  nombre_comercial: string | null
  rol: string
}

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

interface MeResponse {
  usuario: Usuario
  empresa_activa_id: string | null
  rol_activo: string | null
}

/**
 * Sesión global: tokens en cookies (sobreviven un refresh de página),
 * usuario/empresa/rol en useState (reactivo, compartido entre todos
 * los composables/páginas). Los endpoints de /auth/* se llaman aquí
 * directo con $fetch (no vía useApi) para evitar el ciclo
 * refresh-llama-a-refresh.
 */
export function useAuth() {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase

  const accessToken = useCookie<string | null>('access_token', { sameSite: 'lax', default: () => null })
  const refreshTokenCookie = useCookie<string | null>('refresh_token', { sameSite: 'lax', default: () => null })

  const usuario = useState<Usuario | null>('auth_usuario', () => null)
  const empresaActiva = useState<{ id: string, razon_social: string, nombre_comercial: string | null } | null>(
    'auth_empresa_activa', () => null
  )
  const rolActivo = useState<string | null>('auth_rol_activo', () => null)

  function limpiarSesion() {
    accessToken.value = null
    refreshTokenCookie.value = null
    usuario.value = null
    empresaActiva.value = null
    rolActivo.value = null
  }

  async function login(email: string, password: string) {
    const data = await $fetch<TokenResponse>('/auth/login', {
      baseURL,
      method: 'POST',
      body: { email, password }
    })
    accessToken.value = data.access_token
    refreshTokenCookie.value = data.refresh_token
  }

  async function listarEmpresas(): Promise<EmpresaAcceso[]> {
    return await $fetch<EmpresaAcceso[]>('/auth/empresas', {
      baseURL,
      headers: { Authorization: `Bearer ${accessToken.value}` }
    })
  }

  async function seleccionarEmpresa(empresaId: string) {
    const data = await $fetch<TokenResponse>('/auth/seleccionar-empresa', {
      baseURL,
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken.value}` },
      body: { empresa_id: empresaId }
    })
    accessToken.value = data.access_token
    refreshTokenCookie.value = data.refresh_token
    await hidratarSesion()
  }

  /** Vuelve a llamar /auth/me para poblar usuario/empresa/rol -- se
   * usa al arrancar la app (plugin) y tras seleccionar empresa. */
  async function hidratarSesion() {
    if (!accessToken.value) return
    try {
      const me = await $fetch<MeResponse>('/auth/me', {
        baseURL,
        headers: { Authorization: `Bearer ${accessToken.value}` }
      })
      usuario.value = me.usuario
      rolActivo.value = me.rol_activo

      if (me.empresa_activa_id) {
        const empresas = await listarEmpresas()
        const encontrada = empresas.find(e => e.empresa_id === me.empresa_activa_id)
        empresaActiva.value = encontrada
          ? { id: encontrada.empresa_id, razon_social: encontrada.razon_social, nombre_comercial: encontrada.nombre_comercial }
          : null
      } else {
        empresaActiva.value = null
      }
    } catch {
      limpiarSesion()
    }
  }

  /** Intenta refrescar el access token una vez. Devuelve false (y
   * limpia la sesión) si el refresh token también es inválido. */
  async function refrescarSesion(): Promise<boolean> {
    if (!refreshTokenCookie.value) return false
    try {
      const data = await $fetch<TokenResponse>('/auth/refresh', {
        baseURL,
        method: 'POST',
        body: { refresh_token: refreshTokenCookie.value }
      })
      accessToken.value = data.access_token
      refreshTokenCookie.value = data.refresh_token
      return true
    } catch {
      limpiarSesion()
      return false
    }
  }

  async function logout() {
    if (refreshTokenCookie.value) {
      try {
        await $fetch('/auth/logout', {
          baseURL,
          method: 'POST',
          body: { refresh_token: refreshTokenCookie.value }
        })
      } catch {
        // No bloquear el logout local si el server ya no responde.
      }
    }
    limpiarSesion()
  }

  return {
    accessToken,
    usuario,
    empresaActiva,
    rolActivo,
    login,
    listarEmpresas,
    seleccionarEmpresa,
    hidratarSesion,
    refrescarSesion,
    logout,
    limpiarSesion
  }
}

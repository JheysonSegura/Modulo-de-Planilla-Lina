export interface Usuario {
  id: string
  email: string
  nombre_completo: string
  es_superadmin: boolean
  puede_crear_empresas: boolean
  debe_cambiar_password: boolean
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

  // Auditoría de seguridad 2026-08-25 (hallazgo B3): antes dependía de que
  // Nuxt infiriera 'secure' del entorno (no confirmado); fijarlo explícito
  // según si es build de dev (import.meta.dev) evita que la cookie viaje
  // en claro por error, sin romper el login en http://localhost.
  const cookieOptions = { sameSite: 'lax' as const, secure: !import.meta.dev, default: () => null }
  const accessToken = useCookie<string | null>('access_token', cookieOptions)
  const refreshTokenCookie = useCookie<string | null>('refresh_token', cookieOptions)

  const usuario = useState<Usuario | null>('auth_usuario', () => null)
  const empresaActiva = useState<{ id: string, razon_social: string, nombre_comercial: string | null } | null>(
    'auth_empresa_activa', () => null
  )
  const rolActivo = useState<string | null>('auth_rol_activo', () => null)
  // 'consulta' es el único rol sin permiso de escritura -- admin y
  // contador tienen acceso operativo completo (ver CLAUDE.md).
  const puedeEscribir = computed(() => rolActivo.value !== 'consulta')

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

  /** Define la contraseña permanente cuando debe_cambiar_password está
   * activo (reset hecho por un admin/superadmin, ver empresa/usuarios.vue).
   * El backend emite un par de tokens nuevo (sin empresa) -- se recarga
   * usuario/empresa/rol con hidratarSesion() antes de volver. */
  async function cambiarPasswordTemporal(passwordActual: string, passwordNueva: string) {
    const data = await $fetch<TokenResponse>('/auth/cambiar-password-temporal', {
      baseURL,
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken.value}` },
      body: { password_actual: passwordActual, password_nueva: passwordNueva }
    })
    accessToken.value = data.access_token
    refreshTokenCookie.value = data.refresh_token
    await hidratarSesion()
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
    puedeEscribir,
    login,
    listarEmpresas,
    seleccionarEmpresa,
    hidratarSesion,
    refrescarSesion,
    cambiarPasswordTemporal,
    logout,
    limpiarSesion
  }
}

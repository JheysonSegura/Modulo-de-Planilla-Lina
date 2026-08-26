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
  token_type: string
}

interface MeResponse {
  usuario: Usuario
  empresa_activa_id: string | null
  rol_activo: string | null
}

/**
 * Sesión global: el access token vive SOLO en memoria (useState, se
 * pierde en cada recarga de página a propósito -- ver hallazgo A2 de
 * AUDITORIA-SEGURIDAD-2026-08-25.md), el refresh token vive en una
 * cookie httpOnly que pone el backend (routers/auth.py) e invisible
 * para JavaScript. usuario/empresa/rol en useState (reactivo,
 * compartido entre todos los composables/páginas). Los endpoints de
 * /auth/* se llaman aquí directo con $fetch (no vía useApi) para evitar
 * el ciclo refresh-llama-a-refresh. `credentials: 'include'` es
 * necesario en todas las llamadas a /auth/* para que el navegador
 * mande/reciba la cookie httpOnly -- requiere que frontend y API sean
 * subdominios del mismo dominio registrable (ver routers/auth.py).
 */
export function useAuth() {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase

  const accessToken = useState<string | null>('auth_access_token', () => null)

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
    usuario.value = null
    empresaActiva.value = null
    rolActivo.value = null
  }

  async function login(email: string, password: string) {
    const data = await $fetch<TokenResponse>('/auth/login', {
      baseURL,
      method: 'POST',
      credentials: 'include',
      body: { email, password }
    })
    accessToken.value = data.access_token
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
      credentials: 'include',
      headers: { Authorization: `Bearer ${accessToken.value}` },
      body: { empresa_id: empresaId }
    })
    accessToken.value = data.access_token
    await hidratarSesion()
  }

  /** Vuelve a llamar /auth/me para poblar usuario/empresa/rol -- se usa
   * al arrancar la app (plugin) y tras seleccionar empresa. Si todavía
   * no hay access token en memoria (recién arrancó la app, o se acaba
   * de recargar la página), intenta primero un refresh silencioso
   * contra la cookie httpOnly antes de darse por vencido. */
  async function hidratarSesion() {
    if (!accessToken.value) {
      const refrescado = await refrescarSesion()
      if (!refrescado) return
    }
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

  /** Intenta refrescar el access token una vez, usando la cookie
   * httpOnly (nunca visible acá -- el navegador la manda solo). Devuelve
   * false (y limpia la sesión) si no hay cookie o ya no es válida. */
  async function refrescarSesion(): Promise<boolean> {
    try {
      const data = await $fetch<TokenResponse>('/auth/refresh', {
        baseURL,
        method: 'POST',
        credentials: 'include'
      })
      accessToken.value = data.access_token
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
      credentials: 'include',
      headers: { Authorization: `Bearer ${accessToken.value}` },
      body: { password_actual: passwordActual, password_nueva: passwordNueva }
    })
    accessToken.value = data.access_token
    await hidratarSesion()
  }

  async function logout() {
    try {
      await $fetch('/auth/logout', {
        baseURL,
        method: 'POST',
        credentials: 'include'
      })
    } catch {
      // No bloquear el logout local si el server ya no responde.
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

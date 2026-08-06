const RUTAS_PUBLICAS = new Set(['/login'])
const PREFIJOS_ADMIN = ['/auditoria', '/empresa/usuarios']

export default defineNuxtRouteMiddleware((to) => {
  const { accessToken, empresaActiva, rolActivo } = useAuth()

  if (RUTAS_PUBLICAS.has(to.path)) {
    // Ya logueado y con empresa activa -- no tiene sentido volver a /login.
    if (accessToken.value && empresaActiva.value) return navigateTo('/')
    return
  }

  if (!accessToken.value) {
    return navigateTo('/login')
  }

  if (!empresaActiva.value && to.path !== '/seleccionar-empresa') {
    return navigateTo('/seleccionar-empresa')
  }

  // Defensa en el cliente: el backend hoy solo valida rol admin en 2
  // endpoints reales (auditoría, PATCH /empresas/actual) -- el resto
  // de rutas no lo hace todavía (gap documentado, ver CLAUDE.md). No
  // depender solo del backend para ocultar secciones administrativas.
  if (PREFIJOS_ADMIN.some(prefijo => to.path.startsWith(prefijo)) && rolActivo.value !== 'admin') {
    return navigateTo('/')
  }
})

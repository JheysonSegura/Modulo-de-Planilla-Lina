const RUTAS_PUBLICAS = new Set(['/login'])
const PREFIJOS_ADMIN = ['/auditoria', '/empresa/usuarios']
// Rutas dedicadas a crear/editar (no formularios embebidos en una
// página de solo lectura) -- el rol 'consulta' no tiene ningún permiso
// de escritura, así que tampoco debería poder navegar directo a ellas
// por URL, aunque el botón que las enlaza ya esté oculto (puedeEscribir).
const SUFIJOS_ESCRITURA = ['/nuevo', '/nueva', '/editar', '/generar-decimo']

const RUTA_CAMBIO_PASSWORD = '/cambiar-password-temporal'

export default defineNuxtRouteMiddleware((to) => {
  const { accessToken, usuario, empresaActiva, rolActivo } = useAuth()

  if (RUTAS_PUBLICAS.has(to.path)) {
    // Ya logueado y con empresa activa -- no tiene sentido volver a /login.
    if (accessToken.value && empresaActiva.value) return navigateTo('/')
    return
  }

  if (!accessToken.value) {
    return navigateTo('/login')
  }

  // Contraseña temporal pendiente (reset hecho por un admin/superadmin,
  // ver useAuth.cambiarPasswordTemporal): se fuerza esta pantalla antes
  // que cualquier otra cosa, incluso antes de elegir empresa -- el
  // backend ya bloquea todo lo demás (deps.py::get_usuario_actual).
  if (usuario.value?.debe_cambiar_password) {
    if (to.path !== RUTA_CAMBIO_PASSWORD) return navigateTo(RUTA_CAMBIO_PASSWORD)
    return
  }
  if (to.path === RUTA_CAMBIO_PASSWORD) return navigateTo('/')

  if (!empresaActiva.value && to.path !== '/seleccionar-empresa') {
    return navigateTo('/seleccionar-empresa')
  }

  // Defensa en el cliente además de la validación real del backend
  // (require_roles/require_escritura, ver deps.py): no depender solo
  // del backend para ocultar secciones administrativas o de escritura.
  if (PREFIJOS_ADMIN.some(prefijo => to.path.startsWith(prefijo)) && rolActivo.value !== 'admin') {
    return navigateTo('/')
  }

  if (rolActivo.value === 'consulta' && SUFIJOS_ESCRITURA.some(sufijo => to.path.endsWith(sufijo))) {
    return navigateTo('/')
  }
})

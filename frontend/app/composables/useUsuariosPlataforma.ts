export interface UsuarioAdmin {
  id: string
  email: string
  nombre_completo: string
  es_superadmin: boolean
  puede_crear_empresas: boolean
}

export interface PasswordResetPlataformaOut {
  password_temporal: string
  expira_en: string
}

// Solo superadmin (ver CLAUDE.md): gestiona el permiso delegado
// puede_crear_empresas de usuarios con rol admin en alguna empresa.
export function useUsuariosPlataforma() {
  const api = useApi()

  return {
    listarAdmins: () => api.get<UsuarioAdmin[]>('/usuarios'),
    actualizarPermiso: (id: string, puedeCrearEmpresas: boolean) =>
      api.patch<UsuarioAdmin>(`/usuarios/${id}`, { puede_crear_empresas: puedeCrearEmpresas }),
    resetearPassword: (id: string) => api.post<PasswordResetPlataformaOut>(`/usuarios/${id}/resetear-password`)
  }
}

export interface UsuarioEmpresa {
  id: string
  usuario_id: string
  email: string
  nombre_completo: string
  rol: 'admin' | 'contador' | 'consulta'
  activo: boolean
  created_at: string
}

export interface PasswordResetOut {
  password_temporal: string
  expira_en: string
}

export function useUsuariosEmpresa() {
  const api = useApi()

  return {
    listar: () => api.get<UsuarioEmpresa[]>('/empresas/actual/usuarios'),
    agregar: (body: Record<string, unknown>) => api.post<UsuarioEmpresa>('/empresas/actual/usuarios', body),
    actualizar: (id: string, body: Record<string, unknown>) =>
      api.patch<UsuarioEmpresa>(`/empresas/actual/usuarios/${id}`, body),
    resetearPassword: (id: string) =>
      api.post<PasswordResetOut>(`/empresas/actual/usuarios/${id}/resetear-password`)
  }
}

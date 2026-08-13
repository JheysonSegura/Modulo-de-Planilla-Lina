import type { Empresa } from '~/composables/useEmpresa'
import type { UsuarioEmpresa } from '~/composables/useUsuariosEmpresa'

// Solo admins con puede_crear_empresas/es_superadmin (ver CLAUDE.md): dar o
// quitar acceso a un usuario en varias de las empresas que administran, sin
// tener que cambiar de empresa activa por cada una.
export function useMisEmpresas() {
  const api = useApi()

  return {
    listar: () => api.get<Empresa[]>('/mis-empresas'),
    listarUsuarios: (empresaId: string) => api.get<UsuarioEmpresa[]>(`/mis-empresas/${empresaId}/usuarios`),
    agregar: (empresaId: string, body: Record<string, unknown>) =>
      api.post<UsuarioEmpresa>(`/mis-empresas/${empresaId}/usuarios`, body),
    actualizar: (empresaId: string, usuarioEmpresaId: string, body: Record<string, unknown>) =>
      api.patch<UsuarioEmpresa>(`/mis-empresas/${empresaId}/usuarios/${usuarioEmpresaId}`, body)
  }
}

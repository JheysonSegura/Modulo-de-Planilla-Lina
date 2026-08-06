export interface Empleado {
  id: string
  tipo_identificacion: 'cedula' | 'pasaporte'
  identificacion: string
  nombre_completo: string
  fecha_nacimiento: string | null
  fecha_nacionalidad: string | null
  email_personal: string | null
  telefono: string | null
  direccion: string | null
  numero_seguro_social: string | null
  estado: 'activo' | 'inactivo'
  created_at: string
  updated_at: string
}

export function useEmpleados() {
  const api = useApi()

  return {
    listar: () => api.get<Empleado[]>('/empleados'),
    obtener: (id: string) => api.get<Empleado>(`/empleados/${id}`),
    crear: (body: Record<string, unknown>) => api.post<Empleado>('/empleados', body),
    actualizar: (id: string, body: Record<string, unknown>) => api.patch<Empleado>(`/empleados/${id}`, body)
  }
}

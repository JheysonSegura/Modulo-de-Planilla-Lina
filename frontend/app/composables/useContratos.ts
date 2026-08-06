export interface Contrato {
  id: string
  empleado_id: string
  tipo_contrato: 'indefinido' | 'definido' | 'obra_determinada'
  cargo: string
  departamento: string | null
  fecha_inicio: string
  fecha_fin_pactada: string | null
  fecha_fin_real: string | null
  jornada_horas_semana: string
  periodicidad_pago: 'quincenal' | 'mensual'
  fecha_registro_mitradel: string | null
  estado: 'vigente' | 'terminado'
  motivo_terminacion: string | null
  exento_salario_minimo: boolean
  motivo_exencion_salario_minimo: string | null
  es_tecnico: boolean
}

export interface HistorialSalarial {
  id: string
  contrato_id: string
  salario_base: string
  fecha_vigencia_desde: string
  fecha_vigencia_hasta: string | null
  motivo: string | null
}

export interface SalarioVigente {
  contrato_id: string
  fecha_consulta: string
  salario_base: string
}

export function useContratos() {
  const api = useApi()

  return {
    listarDeEmpleado: (empleadoId: string) => api.get<Contrato[]>(`/empleados/${empleadoId}/contratos`),
    crear: (empleadoId: string, body: Record<string, unknown>) =>
      api.post<Contrato>(`/empleados/${empleadoId}/contratos`, body),
    obtener: (contratoId: string) => api.get<Contrato>(`/contratos/${contratoId}`),
    actualizar: (contratoId: string, body: Record<string, unknown>) =>
      api.patch<Contrato>(`/contratos/${contratoId}`, body),
    cambiarSalario: (contratoId: string, body: Record<string, unknown>) =>
      api.post<HistorialSalarial>(`/contratos/${contratoId}/salario`, body),
    historialSalarial: (contratoId: string) =>
      api.get<HistorialSalarial[]>(`/contratos/${contratoId}/historial-salarial`),
    salarioVigente: (contratoId: string) =>
      api.get<SalarioVigente>(`/contratos/${contratoId}/salario-vigente`)
  }
}

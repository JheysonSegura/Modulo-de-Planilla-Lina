export interface TasaVigente {
  id: number
  tipo_tasa: string
  tasa: string
  fecha_inicio: string
  fecha_fin: string | null
  fuente_legal: string | null
}

export interface TramoIsr {
  id: number
  fecha_inicio: string
  fecha_fin: string | null
  monto_desde: string
  monto_hasta: string | null
  tasa_marginal: string
  impuesto_base: string
}

export interface TasaRiesgoProfesional {
  id: number
  clase_riesgo: string
  tasa: string
  fecha_inicio: string
  fecha_fin: string | null
}

export interface SalarioMinimoVigente {
  id: number
  region: string
  actividad: string | null
  tamano_empresa: string | null
  monto_hora: string | null
  monto_mensual: string | null
  fecha_inicio: string
  fecha_fin: string | null
  decreto_ref: string | null
}

export function useTasas() {
  const api = useApi()

  return {
    vigentes: (tipoTasa?: string) => api.get<TasaVigente[]>('/tasas/vigentes', { tipo_tasa: tipoTasa }),
    isr: () => api.get<TramoIsr[]>('/tasas/isr'),
    riesgoProfesional: () => api.get<TasaRiesgoProfesional[]>('/tasas/riesgo-profesional'),
    salarioMinimo: (region?: string, actividad?: string) =>
      api.get<SalarioMinimoVigente[]>('/tasas/salario-minimo', { region, actividad })
  }
}

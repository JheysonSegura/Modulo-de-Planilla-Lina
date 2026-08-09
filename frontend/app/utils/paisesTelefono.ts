export interface CodigoPaisTelefono {
  codigo: string
  pais: string
}

// Lista no exhaustiva de códigos de país para el selector de teléfono.
// Panamá primero porque es el caso por defecto de esta app.
export const paisesTelefono: CodigoPaisTelefono[] = [
  { codigo: '+507', pais: 'Panamá' },
  { codigo: '+506', pais: 'Costa Rica' },
  { codigo: '+503', pais: 'El Salvador' },
  { codigo: '+502', pais: 'Guatemala' },
  { codigo: '+504', pais: 'Honduras' },
  { codigo: '+505', pais: 'Nicaragua' },
  { codigo: '+52', pais: 'México' },
  { codigo: '+57', pais: 'Colombia' },
  { codigo: '+58', pais: 'Venezuela' },
  { codigo: '+593', pais: 'Ecuador' },
  { codigo: '+51', pais: 'Perú' },
  { codigo: '+591', pais: 'Bolivia' },
  { codigo: '+56', pais: 'Chile' },
  { codigo: '+54', pais: 'Argentina' },
  { codigo: '+595', pais: 'Paraguay' },
  { codigo: '+598', pais: 'Uruguay' },
  { codigo: '+55', pais: 'Brasil' },
  { codigo: '+1', pais: 'Estados Unidos / Canadá' },
  { codigo: '+34', pais: 'España' },
  { codigo: '+1809', pais: 'República Dominicana' }
]

export const opcionesPaisesTelefono = paisesTelefono.map(p => ({
  label: `${p.codigo} ${p.pais}`,
  value: p.codigo
}))

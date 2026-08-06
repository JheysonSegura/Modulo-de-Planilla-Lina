<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const route = useRoute()
const empleadoId = route.params.id as string

const { crear } = useContratos()
const toast = useToast()

const schema = z.object({
  tipo_contrato: z.enum(['indefinido', 'definido', 'obra_determinada']),
  cargo: z.string().min(1, 'Obligatorio'),
  departamento: z.string().optional(),
  fecha_inicio: z.string().min(1, 'Obligatorio'),
  fecha_fin_pactada: z.string().optional(),
  jornada_horas_semana: z.number().positive(),
  periodicidad_pago: z.enum(['quincenal', 'mensual']),
  salario_base: z.number().positive('Debe ser mayor que cero'),
  es_tecnico: z.boolean(),
  exento_salario_minimo: z.boolean(),
  motivo_exencion_salario_minimo: z.string().optional()
}).refine(
  data => !data.exento_salario_minimo || !!data.motivo_exencion_salario_minimo,
  { message: 'Obligatorio si el contrato está exento de salario mínimo', path: ['motivo_exencion_salario_minimo'] }
)
type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({
  tipo_contrato: 'indefinido',
  cargo: '',
  departamento: '',
  fecha_inicio: '',
  fecha_fin_pactada: '',
  jornada_horas_semana: 48,
  periodicidad_pago: 'quincenal',
  salario_base: undefined,
  es_tecnico: false,
  exento_salario_minimo: false,
  motivo_exencion_salario_minimo: ''
})

const opcionesTipo = [
  { label: 'Indefinido', value: 'indefinido' },
  { label: 'Definido', value: 'definido' },
  { label: 'Obra determinada', value: 'obra_determinada' }
]
const opcionesPeriodicidad = [
  { label: 'Quincenal', value: 'quincenal' },
  { label: 'Mensual', value: 'mensual' }
]

const guardando = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.departamento) delete body.departamento
    if (!body.fecha_fin_pactada) delete body.fecha_fin_pactada
    if (!body.exento_salario_minimo) delete body.motivo_exencion_salario_minimo
    const contrato = await crear(empleadoId, body)
    toast.add({ title: 'Contrato creado', color: 'success' })
    await navigateTo(`/empleados/${empleadoId}/contratos/${contrato.id}`)
  } catch (error) {
    toast.add({ title: 'No se pudo crear el contrato', description: String(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      Nuevo contrato
    </h1>
    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo de contrato"
          name="tipo_contrato"
        >
          <USelect
            v-model="state.tipo_contrato"
            :items="opcionesTipo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Cargo"
          name="cargo"
        >
          <UInput
            v-model="state.cargo"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Departamento"
          name="departamento"
        >
          <UInput
            v-model="state.departamento"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Fecha de inicio"
          name="fecha_inicio"
        >
          <UInput
            v-model="state.fecha_inicio"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          v-if="state.tipo_contrato !== 'indefinido'"
          label="Fecha de fin pactada"
          name="fecha_fin_pactada"
        >
          <UInput
            v-model="state.fecha_fin_pactada"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Jornada (horas/semana)"
          name="jornada_horas_semana"
        >
          <UInputNumber
            v-model="state.jornada_horas_semana"
            :min="1"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Periodicidad de pago"
          name="periodicidad_pago"
        >
          <USelect
            v-model="state.periodicidad_pago"
            :items="opcionesPeriodicidad"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Salario base mensual"
          name="salario_base"
        >
          <UInputNumber
            v-model="state.salario_base"
            :min="0.01"
            :step="0.01"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Trabajador técnico (Art. 222 CT)"
          name="es_tecnico"
        >
          <USwitch v-model="state.es_tecnico" />
        </UFormField>
        <UFormField
          label="Exento de salario mínimo"
          name="exento_salario_minimo"
        >
          <USwitch v-model="state.exento_salario_minimo" />
        </UFormField>
        <UFormField
          v-if="state.exento_salario_minimo"
          label="Motivo de la exención"
          name="motivo_exencion_salario_minimo"
        >
          <UInput
            v-model="state.motivo_exencion_salario_minimo"
            class="w-full"
            placeholder="Ej. pasantía formal"
          />
        </UFormField>
        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Crear contrato
          </UButton>
          <UButton
            :to="`/empleados/${empleadoId}`"
            color="neutral"
            variant="ghost"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

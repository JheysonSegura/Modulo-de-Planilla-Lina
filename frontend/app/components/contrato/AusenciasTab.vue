<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const props = defineProps<{ contratoId: string }>()

const { listar, registrar } = useAusencias()
const toast = useToast()

const { data: ausencias, refresh } = await useAsyncData(`ausencias-${props.contratoId}`, () => listar(props.contratoId))

const mostrarFormulario = ref(false)
const schema = z.object({
  tipo: z.enum([
    'enfermedad_dentro_fondo', 'enfermedad_excede_fondo', 'embarazo', 'riesgo_profesional',
    'huelga_legal', 'licencia_sindical_o_estado', 'licencia_autorizada_empleador',
    'arresto_o_prision_preventiva', 'injustificada'
  ]),
  fecha_desde: z.string().min(1, 'Obligatorio'),
  fecha_hasta: z.string().min(1, 'Obligatorio'),
  certificado_ref: z.string().optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ tipo: 'injustificada', fecha_desde: '', fecha_hasta: '', certificado_ref: '' })
const guardando = ref(false)

const opcionesTipo = [
  { label: 'Enfermedad (dentro del fondo)', value: 'enfermedad_dentro_fondo' },
  { label: 'Enfermedad (excede el fondo)', value: 'enfermedad_excede_fondo' },
  { label: 'Embarazo', value: 'embarazo' },
  { label: 'Riesgo profesional', value: 'riesgo_profesional' },
  { label: 'Huelga legal', value: 'huelga_legal' },
  { label: 'Licencia sindical o del Estado', value: 'licencia_sindical_o_estado' },
  { label: 'Licencia autorizada por el empleador', value: 'licencia_autorizada_empleador' },
  { label: 'Arresto o prisión preventiva', value: 'arresto_o_prision_preventiva' },
  { label: 'Injustificada', value: 'injustificada' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.certificado_ref) delete body.certificado_ref
    await registrar(props.contratoId, body)
    toast.add({ title: 'Ausencia registrada', color: 'success' })
    mostrarFormulario.value = false
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: String(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-end">
      <UButton
        size="sm"
        icon="i-lucide-plus"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Registrar ausencia
      </UButton>
    </div>

    <UCard v-if="mostrarFormulario">
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo"
          name="tipo"
          class="col-span-2"
        >
          <USelect
            v-model="state.tipo"
            :items="opcionesTipo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Desde"
          name="fecha_desde"
        >
          <UInput
            v-model="state.fecha_desde"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Hasta"
          name="fecha_hasta"
        >
          <UInput
            v-model="state.fecha_hasta"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Referencia de certificado"
          name="certificado_ref"
          class="col-span-2"
        >
          <UInput
            v-model="state.certificado_ref"
            class="w-full"
          />
        </UFormField>
        <UButton
          type="submit"
          class="w-fit"
          :loading="guardando"
        >
          Guardar
        </UButton>
      </UForm>
    </UCard>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Tipo
            </th>
            <th class="py-2 pr-4">
              Desde
            </th>
            <th class="py-2 pr-4">
              Hasta
            </th>
            <th class="py-2">
              Certificado
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="a in ausencias"
            :key="a.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ a.tipo }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(a.fecha_desde) }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(a.fecha_hasta) }}
            </td>
            <td class="py-2 text-gray-500">
              {{ a.certificado_ref || '—' }}
            </td>
          </tr>
          <tr v-if="!ausencias || ausencias.length === 0">
            <td
              colspan="4"
              class="py-8 text-center text-gray-500"
            >
              Sin ausencias registradas.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

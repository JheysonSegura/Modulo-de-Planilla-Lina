<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const props = defineProps<{ contratoId: string }>()
const route = useRoute()
const empleadoId = route.params.id as string

const { listar, registrar, eliminar } = useHorasExtra()
const toast = useToast()

const { data: registros, refresh } = await useAsyncData(`horas-extra-${props.contratoId}`, () => listar(props.contratoId))

const mostrarFormulario = ref(false)
const schema = z.object({
  fecha: z.string().min(1, 'Obligatorio'),
  tipo_hora: z.enum(['diurna', 'nocturna', 'prolongacion_nocturna']),
  tipo_dia: z.enum(['ordinario', 'domingo_descanso', 'feriado_duelo_nacional']),
  horas_horas: z.number().int('Debe ser un número entero').min(0, 'Mínimo 0').max(24, 'Máximo 24'),
  horas_minutos: z.number().int('Debe ser un número entero').min(0, 'Mínimo 0').max(59, 'Máximo 59'),
  observaciones: z.string().optional()
}).refine(data => data.horas_horas > 0 || data.horas_minutos > 0, {
  message: 'Debe registrar al menos algún tiempo',
  path: ['horas_minutos']
}).refine(data => data.horas_horas + data.horas_minutos / 60 <= 24, {
  message: 'No puede superar 24 horas en total',
  path: ['horas_horas']
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ fecha: '', tipo_hora: 'diurna', tipo_dia: 'ordinario', horas_horas: undefined, horas_minutos: undefined, observaciones: '' })
const guardando = ref(false)

const opcionesTipoHora = [
  { label: 'Diurna', value: 'diurna' },
  { label: 'Nocturna', value: 'nocturna' },
  { label: 'Prolongación nocturna', value: 'prolongacion_nocturna' }
]
const opcionesTipoDia = [
  { label: 'Ordinario', value: 'ordinario' },
  { label: 'Domingo/descanso', value: 'domingo_descanso' },
  { label: 'Feriado/duelo nacional', value: 'feriado_duelo_nacional' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = {
      fecha: event.data.fecha,
      tipo_hora: event.data.tipo_hora,
      tipo_dia: event.data.tipo_dia,
      horas: combinarHorasYMinutos(event.data.horas_horas, event.data.horas_minutos),
      observaciones: event.data.observaciones
    }
    if (!body.observaciones) delete body.observaciones
    await registrar(props.contratoId, body)
    toast.add({ title: 'Hora extra registrada', color: 'success' })
    mostrarFormulario.value = false
    state.horas_horas = undefined
    state.horas_minutos = undefined
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

async function borrar(registroId: string) {
  await eliminar(props.contratoId, registroId)
  await refresh()
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
        Registrar hora extra
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
          label="Fecha"
          name="fecha"
        >
          <UInput
            v-model="state.fecha"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Tiempo trabajado">
          <div class="flex gap-2">
            <UFormField
              name="horas_horas"
              label="Horas"
              class="flex-1"
            >
              <UInputNumber
                v-model="state.horas_horas"
                :min="0"
                :max="24"
                :step="1"
                placeholder="0"
                class="w-full"
              />
            </UFormField>
            <UFormField
              name="horas_minutos"
              label="Minutos"
              class="flex-1"
            >
              <UInputNumber
                v-model="state.horas_minutos"
                :min="0"
                :max="59"
                :step="1"
                placeholder="0"
                class="w-full"
              />
            </UFormField>
          </div>
        </UFormField>
        <UFormField
          label="Tipo de hora"
          name="tipo_hora"
        >
          <USelect
            v-model="state.tipo_hora"
            :items="opcionesTipoHora"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Tipo de día"
          name="tipo_dia"
        >
          <USelect
            v-model="state.tipo_dia"
            :items="opcionesTipoDia"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Observaciones"
          name="observaciones"
          class="col-span-2"
        >
          <UInput
            v-model="state.observaciones"
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
              Fecha
            </th>
            <th class="py-2 pr-4">
              Tipo
            </th>
            <th class="py-2 pr-4">
              Día
            </th>
            <th class="py-2 pr-4">
              Horas
            </th>
            <th class="py-2 pr-4">
              Monto
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in registros"
            :key="r.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ formatearFecha(r.fecha) }}
            </td>
            <td class="py-2 pr-4">
              {{ r.tipo_hora }}
            </td>
            <td class="py-2 pr-4">
              {{ r.tipo_dia }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearHorasDecimal(r.horas) }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              ${{ r.monto_calculado }}
            </td>
            <td class="py-2 text-right space-x-1">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-calculator"
                :to="`/empleados/${empleadoId}/contratos/${contratoId}/horas-extra/${r.id}`"
              >
                Ver desglose
              </UButton>
              <UButton
                size="xs"
                color="error"
                variant="ghost"
                icon="i-lucide-trash-2"
                @click="borrar(r.id)"
              />
            </td>
          </tr>
          <tr v-if="!registros || registros.length === 0">
            <td
              colspan="6"
              class="py-8 text-center text-gray-500"
            >
              Sin registros.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

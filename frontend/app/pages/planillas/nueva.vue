<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { generar } = usePlanillas()
const toast = useToast()

const schema = z.object({
  tipo: z.enum(['mensual', 'quincenal']),
  periodo_inicio: z.string().min(1, 'Obligatorio'),
  periodo_fin: z.string().min(1, 'Obligatorio'),
  fecha_pago: z.string().min(1, 'Obligatorio')
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ tipo: 'quincenal', periodo_inicio: '', periodo_fin: '', fecha_pago: '' })

const opcionesTipo = [
  { label: 'Mensual', value: 'mensual' },
  { label: 'Quincenal', value: 'quincenal' }
]

const guardando = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const planilla = await generar(event.data)
    toast.add({ title: 'Planilla generada', color: 'success' })
    await navigateTo(`/planillas/${planilla.id}`)
  } catch (error) {
    toast.add({ title: 'No se pudo generar la planilla', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      Generar planilla
    </h1>
    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo"
          name="tipo"
        >
          <USelect
            v-model="state.tipo"
            :items="opcionesTipo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Período inicio"
          name="periodo_inicio"
        >
          <UInput
            v-model="state.periodo_inicio"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Período fin"
          name="periodo_fin"
        >
          <UInput
            v-model="state.periodo_fin"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Fecha de pago"
          name="fecha_pago"
        >
          <UInput
            v-model="state.fecha_pago"
            type="date"
            class="w-full"
          />
        </UFormField>
        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Generar
          </UButton>
          <UButton
            to="/planillas"
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

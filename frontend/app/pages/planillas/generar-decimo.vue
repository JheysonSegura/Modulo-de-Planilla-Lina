<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { generarPago } = useDecimo()
const toast = useToast()

const schema = z.object({
  cuatrimestre: z.enum(['dic-abr', 'abr-ago', 'ago-dic']),
  anio: z.number().int().min(2020),
  fecha_pago: z.string().min(1, 'Obligatorio')
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ cuatrimestre: 'dic-abr', anio: new Date().getFullYear(), fecha_pago: '' })

const opcionesCuatrimestre = [
  { label: 'Diciembre - Abril (paga 15 de abril)', value: 'dic-abr' },
  { label: 'Abril - Agosto (paga 15 de agosto)', value: 'abr-ago' },
  { label: 'Agosto - Diciembre (paga 15 de diciembre)', value: 'ago-dic' }
]

const guardando = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const planilla = await generarPago(event.data) as { id: string }
    toast.add({ title: 'Décimo generado', color: 'success' })
    await navigateTo(`/planillas/${planilla.id}`)
  } catch (error) {
    toast.add({ title: 'No se pudo generar el décimo', description: String(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      Generar pago de décimo tercer mes
    </h1>
    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Cuatrimestre"
          name="cuatrimestre"
        >
          <USelect
            v-model="state.cuatrimestre"
            :items="opcionesCuatrimestre"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Año"
          name="anio"
        >
          <UInputNumber
            v-model="state.anio"
            :min="2020"
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

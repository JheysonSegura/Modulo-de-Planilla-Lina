<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const props = defineProps<{ contratoId: string }>()

const { listar, registrar, eliminar } = useConceptosVariables()
const { puedeEscribir } = useAuth()
const toast = useToast()

const { data: conceptos, refresh } = await useAsyncData(`conceptos-${props.contratoId}`, () => listar(props.contratoId))

const mostrarFormulario = ref(false)
const schema = z.object({
  fecha: z.string().min(1, 'Obligatorio'),
  tipo: z.enum(['ingreso', 'deduccion']),
  codigo: z.string().min(1, 'Obligatorio'),
  descripcion: z.string().optional(),
  monto: z.number().positive('Debe ser mayor que cero')
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ fecha: '', tipo: 'ingreso', codigo: '', descripcion: '', monto: undefined })
const guardando = ref(false)

const opcionesTipo = [
  { label: 'Ingreso', value: 'ingreso' },
  { label: 'Deducción', value: 'deduccion' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.descripcion) delete body.descripcion
    await registrar(props.contratoId, body)
    toast.add({ title: 'Concepto registrado', color: 'success' })
    mostrarFormulario.value = false
    state.monto = undefined
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

async function borrar(conceptoId: string) {
  await eliminar(props.contratoId, conceptoId)
  await refresh()
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="puedeEscribir"
      class="flex justify-end"
    >
      <UButton
        size="sm"
        icon="i-lucide-plus"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Registrar concepto
      </UButton>
    </div>

    <UCard v-if="mostrarFormulario && puedeEscribir">
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
          label="Código"
          name="codigo"
        >
          <UInput
            v-model="state.codigo"
            class="w-full"
            placeholder="Ej. bono_productividad"
          />
        </UFormField>
        <UFormField
          label="Monto"
          name="monto"
        >
          <UInputNumber
            v-model="state.monto"
            :min="0.01"
            :step="0.01"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Descripción"
          name="descripcion"
          class="col-span-2"
        >
          <UInput
            v-model="state.descripcion"
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
              Código
            </th>
            <th class="py-2 pr-4">
              Monto
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in conceptos"
            :key="c.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ formatearFecha(c.fecha) }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="c.tipo === 'ingreso' ? 'success' : 'error'"
                variant="subtle"
              >
                {{ c.tipo }}
              </UBadge>
            </td>
            <td class="py-2 pr-4">
              {{ c.codigo }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              ${{ c.monto }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="c.aplicado ? 'neutral' : 'warning'"
                variant="subtle"
              >
                {{ c.aplicado ? 'Aplicado' : 'Pendiente' }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                v-if="!c.aplicado && puedeEscribir"
                size="xs"
                color="error"
                variant="ghost"
                icon="i-lucide-trash-2"
                @click="borrar(c.id)"
              />
            </td>
          </tr>
          <tr v-if="!conceptos || conceptos.length === 0">
            <td
              colspan="6"
              class="py-8 text-center text-gray-500"
            >
              Sin conceptos pendientes.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

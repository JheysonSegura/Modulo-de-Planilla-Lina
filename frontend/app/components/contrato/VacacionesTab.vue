<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const props = defineProps<{ contratoId: string }>()

const { provisiones, tomar, acumular } = useVacaciones()
const toast = useToast()

const { data: provs, refresh } = await useAsyncData(`vacaciones-${props.contratoId}`, () => provisiones(props.contratoId))

const mostrarTomar = ref(false)
const mostrarAcumular = ref(false)

const schemaTomar = z.object({ fecha: z.string().min(1, 'Obligatorio'), dias: z.number().positive() })
type SchemaTomar = z.output<typeof schemaTomar>
const stateTomar = reactive<Partial<SchemaTomar>>({ fecha: '', dias: undefined })
const guardandoTomar = ref(false)

const schemaAcumular = z.object({ fecha_acuerdo: z.string().min(1, 'Obligatorio'), notificado_autoridad_trabajo: z.boolean() })
type SchemaAcumular = z.output<typeof schemaAcumular>
const stateAcumular = reactive<Partial<SchemaAcumular>>({ fecha_acuerdo: '', notificado_autoridad_trabajo: false })
const guardandoAcumular = ref(false)

async function onSubmitTomar(event: FormSubmitEvent<SchemaTomar>) {
  guardandoTomar.value = true
  try {
    await tomar(props.contratoId, { fecha: event.data.fecha, dias: event.data.dias })
    toast.add({ title: 'Vacación registrada', color: 'success' })
    mostrarTomar.value = false
    stateTomar.dias = undefined
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: String(error), color: 'error' })
  } finally {
    guardandoTomar.value = false
  }
}

async function onSubmitAcumular(event: FormSubmitEvent<SchemaAcumular>) {
  guardandoAcumular.value = true
  try {
    await acumular(props.contratoId, event.data)
    toast.add({ title: 'Período acumulado', color: 'success' })
    mostrarAcumular.value = false
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo acumular', description: String(error), color: 'error' })
  } finally {
    guardandoAcumular.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-end gap-2">
      <UButton
        size="sm"
        color="neutral"
        variant="soft"
        icon="i-lucide-layers"
        @click="mostrarAcumular = !mostrarAcumular"
      >
        Acumular período (Art. 59)
      </UButton>
      <UButton
        size="sm"
        icon="i-lucide-plus"
        @click="mostrarTomar = !mostrarTomar"
      >
        Registrar vacación tomada
      </UButton>
    </div>

    <UCard v-if="mostrarTomar">
      <UForm
        :schema="schemaTomar"
        :state="stateTomar"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmitTomar"
      >
        <UFormField
          label="Fecha"
          name="fecha"
        >
          <UInput
            v-model="stateTomar.fecha"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Días tomados"
          name="dias"
        >
          <UInputNumber
            v-model="stateTomar.dias"
            :min="0.01"
            :step="0.5"
            class="w-full"
          />
        </UFormField>
        <UButton
          type="submit"
          class="w-fit"
          :loading="guardandoTomar"
        >
          Guardar
        </UButton>
      </UForm>
    </UCard>

    <UCard v-if="mostrarAcumular">
      <p class="text-sm text-gray-500 mb-4">
        Art. 59 CT: requiere un acuerdo explícito con el trabajador y deja al menos 15 días de descanso garantizados en el período actual.
      </p>
      <UForm
        :schema="schemaAcumular"
        :state="stateAcumular"
        class="space-y-4"
        @submit="onSubmitAcumular"
      >
        <UFormField
          label="Fecha del acuerdo"
          name="fecha_acuerdo"
        >
          <UInput
            v-model="stateAcumular.fecha_acuerdo"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Notificado a la autoridad de trabajo"
          name="notificado_autoridad_trabajo"
        >
          <USwitch v-model="stateAcumular.notificado_autoridad_trabajo" />
        </UFormField>
        <UButton
          type="submit"
          class="w-fit"
          :loading="guardandoAcumular"
        >
          Acumular
        </UButton>
      </UForm>
    </UCard>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Período desde
            </th>
            <th class="py-2 pr-4">
              Días acumulados
            </th>
            <th class="py-2 pr-4">
              Días gozados
            </th>
            <th class="py-2 pr-4">
              Saldo disponible
            </th>
            <th class="py-2 pr-4">
              Monto provisionado
            </th>
            <th class="py-2">
              Estado
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in provs"
            :key="p.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ formatearFecha(p.fecha_inicio_periodo) }}
            </td>
            <td class="py-2 pr-4">
              {{ p.dias_acumulados }}
            </td>
            <td class="py-2 pr-4">
              {{ p.dias_gozados }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ p.saldo_disponible }}
            </td>
            <td class="py-2 pr-4">
              ${{ p.monto_provisionado }}
            </td>
            <td class="py-2">
              <UBadge variant="subtle">
                {{ p.estado }}
              </UBadge>
            </td>
          </tr>
          <tr v-if="!provs || provs.length === 0">
            <td
              colspan="6"
              class="py-8 text-center text-gray-500"
            >
              Sin provisiones todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

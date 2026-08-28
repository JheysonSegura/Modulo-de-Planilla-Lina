<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Contrato } from '~/composables/useContratos'

const props = defineProps<{ contrato: Contrato }>()
const emit = defineEmits<{ 'contrato-actualizado': [] }>()

const { salarioVigente, cambiarSalario, historialCargos, cambiarCargo } = useContratos()
const { puedeEscribir } = useAuth()
const toast = useToast()

const { data: salario, refresh: refrescarSalario } = await useAsyncData(
  `salario-vigente-${props.contrato.id}`, () => salarioVigente(props.contrato.id)
)

const mostrarFormulario = ref(false)
const schema = z.object({
  salario_base: z.number().positive('Debe ser mayor que cero'),
  fecha_vigencia_desde: z.string().min(1, 'Obligatorio'),
  motivo: z.string().min(1)
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ salario_base: undefined, fecha_vigencia_desde: '', motivo: 'ajuste_salarial' })
const guardando = ref(false)

// El salario de un contrato vigente nunca puede bajar (ver CLAUDE.md) --
// el backend es la autoridad final, este mínimo solo evita el viaje
// redondo obvio de escribir un valor que ya se sabe inválido.
const salarioMinimoNuevo = computed(() => {
  const actual = Number(salario.value?.salario_base ?? 0)
  return Math.round((actual + 0.01) * 100) / 100
})

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    await cambiarSalario(props.contrato.id, event.data)
    toast.add({ title: 'Salario actualizado', color: 'success' })
    mostrarFormulario.value = false
    await refrescarSalario()
  } catch (error) {
    toast.add({ title: 'No se pudo cambiar el salario', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

// Cargo: un cambio de puesto es una adenda al mismo contrato (no un
// contrato nuevo) -- ver historial_cargos. Sin mínimo/máximo, a
// diferencia del salario, un cargo no tiene orden.
const { data: historialCargo, refresh: refrescarHistorialCargo } = await useAsyncData(
  `historial-cargo-${props.contrato.id}`, () => historialCargos(props.contrato.id)
)

const mostrarFormularioCargo = ref(false)
const schemaCargo = z.object({
  cargo: z.string().min(1, 'Obligatorio'),
  fecha_vigencia_desde: z.string().min(1, 'Obligatorio'),
  motivo: z.string().min(1)
})
type SchemaCargo = z.output<typeof schemaCargo>
const stateCargo = reactive<Partial<SchemaCargo>>({ cargo: '', fecha_vigencia_desde: '', motivo: 'cambio_puesto' })
const guardandoCargo = ref(false)

async function onSubmitCargo(event: FormSubmitEvent<SchemaCargo>) {
  guardandoCargo.value = true
  try {
    await cambiarCargo(props.contrato.id, event.data)
    toast.add({ title: 'Cargo actualizado', color: 'success' })
    mostrarFormularioCargo.value = false
    await refrescarHistorialCargo()
    emit('contrato-actualizado')
  } catch (error) {
    toast.add({ title: 'No se pudo cambiar el cargo', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardandoCargo.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <UCard>
      <template #header>
        <span class="font-medium">Datos del contrato</span>
      </template>
      <dl class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <dt class="text-gray-500">
            Tipo
          </dt><dd>{{ contrato.tipo_contrato }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Departamento
          </dt><dd>{{ contrato.departamento || '—' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Fecha de inicio
          </dt><dd>{{ formatearFecha(contrato.fecha_inicio) }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Fecha fin pactada
          </dt><dd>{{ formatearFecha(contrato.fecha_fin_pactada) }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Jornada
          </dt><dd>{{ contrato.jornada_horas_semana }} h/semana</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Periodicidad de pago
          </dt><dd>{{ contrato.periodicidad_pago }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Trabajador técnico
          </dt><dd>{{ contrato.es_tecnico ? 'Sí' : 'No' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Exento salario mínimo
          </dt><dd>{{ contrato.exento_salario_minimo ? 'Sí' : 'No' }}</dd>
        </div>
      </dl>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">Cargo actual</span>
          <UButton
            v-if="contrato.estado === 'vigente' && puedeEscribir"
            size="xs"
            variant="soft"
            @click="mostrarFormularioCargo = !mostrarFormularioCargo"
          >
            Cambiar cargo
          </UButton>
        </div>
      </template>
      <p class="text-2xl font-semibold text-gray-900 dark:text-white">
        {{ contrato.cargo }}
      </p>

      <UForm
        v-if="mostrarFormularioCargo"
        :schema="schemaCargo"
        :state="stateCargo"
        class="space-y-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-800"
        @submit="onSubmitCargo"
      >
        <UFormField
          label="Nuevo cargo"
          name="cargo"
        >
          <UInput
            v-model="stateCargo.cargo"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Vigente desde"
          name="fecha_vigencia_desde"
        >
          <UInput
            v-model="stateCargo.fecha_vigencia_desde"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Motivo"
          name="motivo"
        >
          <UInput
            v-model="stateCargo.motivo"
            class="w-full"
          />
        </UFormField>
        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardandoCargo"
          >
            Guardar
          </UButton>
          <UButton
            color="neutral"
            variant="ghost"
            @click="mostrarFormularioCargo = false"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>

      <table class="w-full text-sm mt-4 pt-4 border-t border-gray-200 dark:border-gray-800">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Cargo
            </th>
            <th class="py-2 pr-4">
              Vigente desde
            </th>
            <th class="py-2 pr-4">
              Vigente hasta
            </th>
            <th class="py-2">
              Motivo
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="h in historialCargo"
            :key="h.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ h.cargo }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(h.fecha_vigencia_desde) }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(h.fecha_vigencia_hasta, 'Vigente') }}
            </td>
            <td class="py-2 text-gray-500">
              {{ h.motivo || '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">Salario vigente</span>
          <UButton
            v-if="contrato.estado === 'vigente' && puedeEscribir"
            size="xs"
            variant="soft"
            @click="mostrarFormulario = !mostrarFormulario"
          >
            Cambiar salario
          </UButton>
        </div>
      </template>
      <p class="text-2xl font-semibold text-gray-900 dark:text-white">
        ${{ salario?.salario_base }} <span class="text-sm font-normal text-gray-500">/mes</span>
      </p>

      <UForm
        v-if="mostrarFormulario"
        :schema="schema"
        :state="state"
        class="space-y-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-800"
        @submit="onSubmit"
      >
        <UFormField
          label="Nuevo salario base"
          name="salario_base"
        >
          <UInputNumber
            v-model="state.salario_base"
            :min="salarioMinimoNuevo"
            :step="0.01"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Vigente desde"
          name="fecha_vigencia_desde"
        >
          <UInput
            v-model="state.fecha_vigencia_desde"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Motivo"
          name="motivo"
        >
          <UInput
            v-model="state.motivo"
            class="w-full"
          />
        </UFormField>
        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Guardar
          </UButton>
          <UButton
            color="neutral"
            variant="ghost"
            @click="mostrarFormulario = false"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

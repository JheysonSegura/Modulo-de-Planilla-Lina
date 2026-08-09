<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Contrato } from '~/composables/useContratos'

const props = defineProps<{ contrato: Contrato }>()

const { salarioVigente, cambiarSalario } = useContratos()
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
          <span class="font-medium">Salario vigente</span>
          <UButton
            v-if="contrato.estado === 'vigente'"
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
            :min="0.01"
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
        <UButton
          type="submit"
          :loading="guardando"
        >
          Guardar
        </UButton>
      </UForm>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { obtenerActual, actualizarActual } = useEmpresa()
const { rolActivo } = useAuth()
const toast = useToast()

const { data: empresa, refresh } = await useAsyncData('empresa-actual', () => obtenerActual())

const editando = ref(false)
const schema = z.object({
  region: z.string().optional(),
  actividad_economica: z.string().optional(),
  tamano_empresa: z.enum(['Pequeña Empresa', 'Gran Empresa']).optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({})
const guardando = ref(false)

function abrirEdicion() {
  state.region = empresa.value?.region ?? undefined
  state.actividad_economica = empresa.value?.actividad_economica ?? undefined
  state.tamano_empresa = (empresa.value?.tamano_empresa as Schema['tamano_empresa']) ?? undefined
  editando.value = true
}

const opcionesTamano = [
  { label: 'Pequeña Empresa', value: 'Pequeña Empresa' },
  { label: 'Gran Empresa', value: 'Gran Empresa' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    await actualizarActual(event.data)
    toast.add({ title: 'Empresa actualizada', color: 'success' })
    editando.value = false
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo actualizar', description: String(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div
    v-if="empresa"
    class="max-w-2xl"
  >
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      {{ empresa.nombre_comercial || empresa.razon_social }}
    </h1>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">Datos de la empresa</span>
          <UButton
            v-if="rolActivo === 'admin' && !editando"
            size="xs"
            variant="soft"
            @click="abrirEdicion"
          >
            Editar
          </UButton>
        </div>
      </template>

      <dl
        v-if="!editando"
        class="grid grid-cols-2 gap-4 text-sm"
      >
        <div>
          <dt class="text-gray-500">
            Razón social
          </dt><dd>{{ empresa.razon_social }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            RUC
          </dt><dd>{{ empresa.ruc }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Clase de riesgo
          </dt><dd>{{ empresa.clase_riesgo || '—' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Región
          </dt><dd>{{ empresa.region || '—' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Actividad económica
          </dt><dd>{{ empresa.actividad_economica || '—' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Tamaño de empresa
          </dt><dd>{{ empresa.tamano_empresa || '—' }}</dd>
        </div>
      </dl>

      <UForm
        v-else
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <p class="text-xs text-gray-500">
          Solo estos 3 campos son editables desde el sistema -- determinan qué fila de salario mínimo aplica.
        </p>
        <UFormField
          label="Región"
          name="region"
        >
          <UInput
            v-model="state.region"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Actividad económica"
          name="actividad_economica"
        >
          <UInput
            v-model="state.actividad_economica"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Tamaño de empresa"
          name="tamano_empresa"
        >
          <USelect
            v-model="state.tamano_empresa"
            :items="opcionesTamano"
            value-key="value"
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
            @click="editando = false"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

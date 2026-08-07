<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { obtenerActual, actualizarActual } = useEmpresa()
const { obtenerLogoUrl, subirLogo } = useReportes()
const { rolActivo } = useAuth()
const toast = useToast()

const { data: empresa, refresh } = await useAsyncData('empresa-actual', () => obtenerActual())

const logoUrl = ref<string | null>(null)
const subiendoLogo = ref(false)
const inputLogo = ref<HTMLInputElement>()

async function cargarLogo() {
  logoUrl.value = empresa.value?.tiene_logo ? await obtenerLogoUrl() : null
}
await cargarLogo()

async function onSeleccionarLogo(event: Event) {
  const archivo = (event.target as HTMLInputElement).files?.[0]
  if (!archivo) return
  subiendoLogo.value = true
  try {
    await subirLogo(archivo)
    toast.add({ title: 'Logo actualizado', color: 'success' })
    await refresh()
    await cargarLogo()
  } catch (error) {
    toast.add({ title: 'No se pudo subir el logo', description: String(error), color: 'error' })
  } finally {
    subiendoLogo.value = false
    if (inputLogo.value) inputLogo.value.value = ''
  }
}

const editando = ref(false)
const schema = z.object({
  region: z.string().optional(),
  actividad_economica: z.string().optional(),
  tamano_empresa: z.enum(['Pequeña Empresa', 'Gran Empresa']).optional(),
  dv: z.string().optional(),
  direccion: z.string().optional(),
  telefono: z.string().optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({})
const guardando = ref(false)

function abrirEdicion() {
  state.region = empresa.value?.region ?? undefined
  state.actividad_economica = empresa.value?.actividad_economica ?? undefined
  state.tamano_empresa = (empresa.value?.tamano_empresa as Schema['tamano_empresa']) ?? undefined
  state.dv = empresa.value?.dv ?? undefined
  state.direccion = empresa.value?.direccion ?? undefined
  state.telefono = empresa.value?.telefono ?? undefined
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
          </dt><dd>{{ empresa.ruc }}{{ empresa.dv ? ` DV ${empresa.dv}` : '' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Dirección
          </dt><dd>{{ empresa.direccion || '—' }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Teléfono
          </dt><dd>{{ empresa.telefono || '—' }}</dd>
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
          Región/actividad/tamaño determinan qué fila de salario mínimo aplica. DV/dirección/teléfono
          se imprimen en el membrete de recibos y reportes (Fase 16).
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
        <UFormField
          label="DV (dígito verificador del RUC)"
          name="dv"
        >
          <UInput
            v-model="state.dv"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Dirección"
          name="direccion"
        >
          <UInput
            v-model="state.direccion"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Teléfono"
          name="telefono"
        >
          <UInput
            v-model="state.telefono"
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

    <UCard class="mt-4">
      <template #header>
        <span class="font-medium">Logo (membrete de recibos y reportes)</span>
      </template>
      <div class="flex items-center gap-4">
        <img
          v-if="logoUrl"
          :src="logoUrl"
          alt="Logo de la empresa"
          class="h-16 max-w-40 object-contain border rounded"
        >
        <span
          v-else
          class="text-sm text-gray-500"
        >Esta empresa no tiene logo cargado.</span>
        <UButton
          v-if="rolActivo === 'admin'"
          size="xs"
          variant="soft"
          :loading="subiendoLogo"
          @click="inputLogo?.click()"
        >
          {{ logoUrl ? 'Cambiar logo' : 'Subir logo' }}
        </UButton>
        <input
          ref="inputLogo"
          type="file"
          accept="image/png,image/jpeg,image/svg+xml,image/webp"
          class="hidden"
          @change="onSeleccionarLogo"
        >
      </div>
    </UCard>
  </div>
</template>

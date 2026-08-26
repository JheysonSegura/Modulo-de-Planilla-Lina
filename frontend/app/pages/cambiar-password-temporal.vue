<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'publico' })

const { cambiarPasswordTemporal } = useAuth()

const schema = z.object({
  password_actual: z.string().min(1, 'Obligatorio'),
  password_nueva: z.string().min(10, 'Mínimo 10 caracteres'),
  confirmar: z.string().min(1, 'Obligatorio')
}).refine(d => d.password_nueva === d.confirmar, {
  message: 'Las contraseñas no coinciden',
  path: ['confirmar']
}).refine(d => d.password_nueva !== d.password_actual, {
  message: 'Debe ser distinta de la contraseña temporal',
  path: ['password_nueva']
})
type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({ password_actual: '', password_nueva: '', confirmar: '' })
const cargando = ref(false)
const error = ref<string | null>(null)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  cargando.value = true
  error.value = null
  try {
    await cambiarPasswordTemporal(event.data.password_actual, event.data.password_nueva)
    await navigateTo('/seleccionar-empresa')
  } catch (e) {
    error.value = extraerMensajeError(e)
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <UCard>
    <p class="text-sm text-gray-500 mb-4">
      Estás usando una contraseña temporal. Definí una contraseña permanente para continuar.
    </p>
    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      :title="error"
      class="mb-4"
    />
    <UForm
      :schema="schema"
      :state="state"
      class="space-y-4"
      @submit="onSubmit"
    >
      <UFormField
        label="Contraseña temporal"
        name="password_actual"
      >
        <UInput
          v-model="state.password_actual"
          type="password"
          class="w-full"
          autofocus
        />
      </UFormField>
      <UFormField
        label="Nueva contraseña"
        name="password_nueva"
      >
        <UInput
          v-model="state.password_nueva"
          type="password"
          class="w-full"
        />
      </UFormField>
      <UFormField
        label="Confirmar nueva contraseña"
        name="confirmar"
      >
        <UInput
          v-model="state.confirmar"
          type="password"
          class="w-full"
        />
      </UFormField>
      <UButton
        type="submit"
        block
        :loading="cargando"
      >
        Guardar y continuar
      </UButton>
    </UForm>
  </UCard>
</template>

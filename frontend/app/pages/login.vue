<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'publico' })

const { login, listarEmpresas, seleccionarEmpresa } = useAuth()

const schema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(1, 'La contraseña es obligatoria')
})
type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({ email: '', password: '' })
const cargando = ref(false)
const error = ref<string | null>(null)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  cargando.value = true
  error.value = null
  try {
    await login(event.data.email, event.data.password)
    const empresas = await listarEmpresas()
    if (empresas.length === 1) {
      await seleccionarEmpresa(empresas[0]!.empresa_id)
      await navigateTo('/')
    } else {
      await navigateTo('/seleccionar-empresa')
    }
  } catch {
    error.value = 'Email o contraseña incorrectos.'
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <UCard>
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
        label="Email"
        name="email"
      >
        <UInput
          v-model="state.email"
          type="email"
          class="w-full"
          autofocus
        />
      </UFormField>
      <UFormField
        label="Contraseña"
        name="password"
      >
        <UInput
          v-model="state.password"
          type="password"
          class="w-full"
        />
      </UFormField>
      <UButton
        type="submit"
        block
        :loading="cargando"
      >
        Entrar
      </UButton>
    </UForm>
  </UCard>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

definePageMeta({ layout: 'publico' })

const { login, listarEmpresas, seleccionarEmpresa, usuario, hidratarSesion } = useAuth()

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
    // hidratarSesion puebla usuario.value (login() por sí solo solo fija
    // los tokens) -- se necesita para saber si el usuario puede crear
    // empresas (es_superadmin o el permiso delegado puede_crear_empresas,
    // ver CLAUDE.md), y en ese caso nunca saltar la pantalla de
    // selección aunque el sistema solo tenga una empresa, porque ahí
    // vive el botón de "Crear empresa nueva".
    await hidratarSesion()
    if (usuario.value?.debe_cambiar_password) {
      // Se chequea ANTES de listarEmpresas(): con una temporal pendiente
      // el backend bloquea todo endpoint que no sea /auth/me, /auth/logout
      // o /auth/cambiar-password-temporal (ver deps.py::get_usuario_actual),
      // así que /auth/empresas daría 403 y caería en el catch genérico.
      await navigateTo('/cambiar-password-temporal')
      return
    }
    const empresas = await listarEmpresas()
    const puedeCrearEmpresas = usuario.value?.es_superadmin || usuario.value?.puede_crear_empresas
    if (empresas.length === 1 && !puedeCrearEmpresas) {
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

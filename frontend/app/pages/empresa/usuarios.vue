<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { listar, agregar, actualizar } = useUsuariosEmpresa()
const { usuario: usuarioActual } = useAuth()
const toast = useToast()

const { data: usuarios, refresh } = await useAsyncData('usuarios-empresa', () => listar())

const mostrarFormulario = ref(false)
const schema = z.object({
  email: z.string().email('Email inválido'),
  rol: z.enum(['admin', 'contador', 'consulta']),
  nombre_completo: z.string().optional(),
  password: z.string().min(8, 'Mínimo 8 caracteres').optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ email: '', rol: 'consulta', nombre_completo: '', password: '' })
const guardando = ref(false)

const opcionesRol = [
  { label: 'Admin', value: 'admin' },
  { label: 'Contador', value: 'contador' },
  { label: 'Consulta', value: 'consulta' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.nombre_completo) delete body.nombre_completo
    if (!body.password) delete body.password
    await agregar(body)
    toast.add({ title: 'Usuario agregado', color: 'success' })
    mostrarFormulario.value = false
    Object.assign(state, { email: '', rol: 'consulta', nombre_completo: '', password: '' })
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo agregar el usuario', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

function cancelar() {
  mostrarFormulario.value = false
  Object.assign(state, { email: '', rol: 'consulta', nombre_completo: '', password: '' })
}

async function cambiarRol(id: string, rol: string) {
  await actualizar(id, { rol })
  await refresh()
}

async function alternarActivo(id: string, activo: boolean) {
  await actualizar(id, { activo: !activo })
  await refresh()
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
        Usuarios de la empresa
      </h1>
      <UButton
        size="sm"
        icon="i-lucide-user-plus"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Agregar usuario
      </UButton>
    </div>

    <UCard
      v-if="mostrarFormulario"
      class="mb-4"
    >
      <p class="text-xs text-gray-500 mb-3">
        Si el email ya tiene cuenta en el sistema, solo se vincula con el rol elegido. Si es nuevo, completa nombre y contraseña.
      </p>
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
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
          />
        </UFormField>
        <UFormField
          label="Rol"
          name="rol"
        >
          <USelect
            v-model="state.rol"
            :items="opcionesRol"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Nombre completo (si es nuevo)"
          name="nombre_completo"
        >
          <UInput
            v-model="state.nombre_completo"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Contraseña (si es nuevo)"
          name="password"
        >
          <UInput
            v-model="state.password"
            type="password"
            class="w-full"
          />
        </UFormField>
        <div class="flex gap-2 col-span-2">
          <UButton
            type="submit"
            class="w-fit"
            :loading="guardando"
          >
            Agregar
          </UButton>
          <UButton
            type="button"
            class="w-fit"
            color="neutral"
            variant="soft"
            :disabled="guardando"
            @click="cancelar"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Nombre
            </th>
            <th class="py-2 pr-4">
              Email
            </th>
            <th class="py-2 pr-4">
              Rol
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in usuarios"
            :key="u.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ u.nombre_completo }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ u.email }}
            </td>
            <td class="py-2 pr-4">
              <USelect
                :model-value="u.rol"
                :items="opcionesRol"
                value-key="value"
                size="xs"
                :disabled="u.usuario_id === usuarioActual?.id"
                @update:model-value="(rol: string) => cambiarRol(u.id, rol)"
              />
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="u.activo ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ u.activo ? 'Activo' : 'Inactivo' }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                v-if="u.usuario_id !== usuarioActual?.id"
                size="xs"
                color="neutral"
                variant="ghost"
                @click="alternarActivo(u.id, u.activo)"
              >
                {{ u.activo ? 'Desactivar' : 'Reactivar' }}
              </UButton>
              <span
                v-else
                class="text-xs text-gray-400"
              >Tú</span>
            </td>
          </tr>
          <tr v-if="!usuarios || usuarios.length === 0">
            <td
              colspan="5"
              class="py-8 text-center text-gray-500"
            >
              Sin usuarios.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

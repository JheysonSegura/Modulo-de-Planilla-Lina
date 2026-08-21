<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { EmpresaAcceso } from '~/composables/useAuth'

definePageMeta({ layout: 'publico' })

const { listarEmpresas, seleccionarEmpresa, accessToken, usuario, hidratarSesion } = useAuth()
const { crear } = useEmpresa()
const { listarAdmins, actualizarPermiso, resetearPassword } = useUsuariosPlataforma()
const toast = useToast()

if (!accessToken.value) {
  await navigateTo('/login')
}
// Justo después de un login fresco (sin pasar por el plugin de arranque)
// `usuario` todavía no está poblado -- se necesita para saber si mostrar
// el botón de crear empresa (usuario.es_superadmin).
if (!usuario.value) {
  await hidratarSesion()
}

const { data: empresas, pending, error, refresh } = await useAsyncData<EmpresaAcceso[]>(
  'auth-empresas',
  () => listarEmpresas()
)

// es_superadmin puede TODO; puede_crear_empresas es el permiso delegado
// más angosto (solo crear, ver CLAUDE.md) -- ambos ven el botón de crear.
const puedeCrearEmpresas = computed(() => usuario.value?.es_superadmin || usuario.value?.puede_crear_empresas)

const seleccionando = ref<string | null>(null)

async function elegir(empresaId: string) {
  seleccionando.value = empresaId
  try {
    await seleccionarEmpresa(empresaId)
    await navigateTo('/')
  } finally {
    seleccionando.value = null
  }
}

// Solo superadmin (ver CLAUDE.md): crear una empresa nueva.
const mostrarFormulario = ref(false)
const schema = z.object({
  razon_social: z.string().min(1, 'Obligatorio'),
  nombre_comercial: z.string().optional(),
  ruc: z.string().min(1, 'Obligatorio'),
  dv: z.string().optional()
})
type Schema = z.output<typeof schema>
const estadoInicial = { razon_social: '', nombre_comercial: '', ruc: '', dv: '' }
const state = reactive<Partial<Schema>>({ ...estadoInicial })
const creando = ref(false)

function cancelar() {
  mostrarFormulario.value = false
  Object.assign(state, estadoInicial)
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  creando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.nombre_comercial) delete body.nombre_comercial
    if (!body.dv) delete body.dv
    await crear(body)
    toast.add({ title: 'Empresa creada', color: 'success' })
    cancelar()
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo crear la empresa', description: extraerMensajeError(error), color: 'error' })
  } finally {
    creando.value = false
  }
}

// Solo superadmin (ver CLAUDE.md): activar/desactivar a admins puntuales
// el permiso delegado de crear empresas.
const { data: admins, refresh: refrescarAdmins } = await useAsyncData(
  'plataforma-admins',
  () => (usuario.value?.es_superadmin ? listarAdmins() : Promise.resolve([]))
)
const actualizandoPermiso = ref<string | null>(null)

async function togglePermiso(id: string, valorActual: boolean) {
  actualizandoPermiso.value = id
  try {
    await actualizarPermiso(id, !valorActual)
    await refrescarAdmins()
  } catch (error) {
    toast.add({ title: 'No se pudo actualizar el permiso', description: extraerMensajeError(error), color: 'error' })
  } finally {
    actualizandoPermiso.value = null
  }
}

const modalPasswordAbierto = ref(false)
const passwordTemporalGenerada = ref('')
const reseteandoPassword = ref<string | null>(null)

async function onResetearPassword(id: string) {
  reseteandoPassword.value = id
  try {
    const resultado = await resetearPassword(id)
    passwordTemporalGenerada.value = resultado.password_temporal
    modalPasswordAbierto.value = true
  } catch (error) {
    toast.add({ title: 'No se pudo resetear la contraseña', description: extraerMensajeError(error), color: 'error' })
  } finally {
    reseteandoPassword.value = null
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-4">
      <p class="text-gray-600 dark:text-gray-400">
        Elige la empresa con la que quieres trabajar
      </p>
      <UButton
        v-if="puedeCrearEmpresas"
        size="sm"
        icon="i-lucide-building-2"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Crear empresa nueva
      </UButton>
    </div>

    <UCard v-if="mostrarFormulario">
      <p class="text-xs text-gray-500 mb-3">
        Quedas vinculado como admin de la empresa nueva -- usa "Agregar usuario" desde ahí para darle acceso a otros.
      </p>
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Razón social"
          name="razon_social"
        >
          <UInput
            v-model="state.razon_social"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Nombre comercial"
          name="nombre_comercial"
        >
          <UInput
            v-model="state.nombre_comercial"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="RUC"
          name="ruc"
        >
          <UInput
            v-model="state.ruc"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="DV"
          name="dv"
        >
          <UInput
            v-model="state.dv"
            class="w-full"
          />
        </UFormField>
        <div class="flex gap-2 col-span-2">
          <UButton
            type="submit"
            class="w-fit"
            :loading="creando"
          >
            Crear
          </UButton>
          <UButton
            type="button"
            class="w-fit"
            color="neutral"
            variant="soft"
            :disabled="creando"
            @click="cancelar"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      title="No se pudieron cargar tus empresas."
    />
    <div
      v-else-if="pending"
      class="text-center text-gray-500"
    >
      Cargando...
    </div>

    <UCard
      v-for="empresa in empresas"
      :key="empresa.empresa_id"
      class="cursor-pointer hover:ring-2 hover:ring-primary transition"
      @click="elegir(empresa.empresa_id)"
    >
      <div class="flex items-center justify-between">
        <div>
          <div class="font-medium text-gray-900 dark:text-white">
            {{ empresa.nombre_comercial || empresa.razon_social }}
          </div>
          <div class="text-sm text-gray-500">
            {{ empresa.razon_social }}
          </div>
        </div>
        <div class="flex items-center gap-3">
          <UBadge
            color="secondary"
            variant="subtle"
          >
            {{ empresa.rol }}
          </UBadge>
          <UIcon
            v-if="seleccionando === empresa.empresa_id"
            name="i-lucide-loader-2"
            class="animate-spin"
          />
          <UIcon
            v-else
            name="i-lucide-chevron-right"
          />
        </div>
      </div>
    </UCard>

    <p
      v-if="empresas && empresas.length === 0 && !puedeCrearEmpresas"
      class="text-center text-gray-500"
    >
      No tienes acceso a ninguna empresa todavía. Contacta a tu administrador.
    </p>
    <p
      v-else-if="empresas && empresas.length === 0"
      class="text-center text-gray-500"
    >
      No hay ninguna empresa creada todavía. Usa "Crear empresa nueva" para dar de alta la primera.
    </p>

    <template v-if="usuario?.es_superadmin">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white pt-4">
        Permisos de administradores
      </h2>
      <p class="text-sm text-gray-500 -mt-2">
        Activa o desactiva, por usuario, el permiso de crear empresas nuevas.
      </p>
      <UCard>
        <div
          v-for="a in admins"
          :key="a.id"
          class="py-3 border-b border-gray-100 dark:border-gray-800 last:border-0 first:pt-0 last:pb-0"
        >
          <div class="min-w-0 mb-2">
            <div class="font-medium text-gray-900 dark:text-white break-words">
              {{ a.nombre_completo }}
            </div>
            <div class="text-sm text-gray-500 break-words">
              {{ a.email }}
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <UBadge
              v-if="a.es_superadmin"
              color="warning"
              variant="subtle"
            >
              Superadmin
            </UBadge>
            <template v-else>
              <UBadge
                :color="a.puede_crear_empresas ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ a.puede_crear_empresas ? 'Puede crear empresas' : 'Sin permiso' }}
              </UBadge>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                :loading="actualizandoPermiso === a.id"
                @click="togglePermiso(a.id, a.puede_crear_empresas)"
              >
                {{ a.puede_crear_empresas ? 'Desactivar' : 'Activar' }}
              </UButton>
            </template>
            <UButton
              v-if="a.id !== usuario?.id"
              size="xs"
              color="neutral"
              variant="ghost"
              :loading="reseteandoPassword === a.id"
              @click="onResetearPassword(a.id)"
            >
              Resetear password
            </UButton>
          </div>
        </div>
        <p
          v-if="!admins || admins.length === 0"
          class="py-8 text-center text-gray-500"
        >
          Sin usuarios con rol admin todavía.
        </p>
      </UCard>
    </template>

    <PasswordTemporalModal
      v-model:open="modalPasswordAbierto"
      :password-temporal="passwordTemporalGenerada"
    />
  </div>
</template>

<script setup lang="ts">
import type { Empresa } from '~/composables/useEmpresa'
import type { UsuarioEmpresa } from '~/composables/useUsuariosEmpresa'

const { usuario } = useAuth()
if (!usuario.value?.es_superadmin && !usuario.value?.puede_crear_empresas) {
  await navigateTo('/')
}

const { listar, listarUsuarios, agregar, actualizar } = useMisEmpresas()
const toast = useToast()

interface Fila {
  empresa: Empresa
  vinculo: UsuarioEmpresa | null
  rolSeleccionado: string
}

const opcionesRol = [
  { label: 'Sin acceso', value: 'sin_acceso' },
  { label: 'Contador', value: 'contador' },
  { label: 'Consulta', value: 'consulta' }
]

const email = ref('')
const buscando = ref(false)
const buscado = ref(false)
const filas = ref<Fila[]>([])
const actualizandoEmpresaId = ref<string | null>(null)

async function buscar() {
  if (!email.value) return
  buscando.value = true
  try {
    const misEmpresas = await listar()
    const nuevasFilas: Fila[] = []
    for (const empresa of misEmpresas) {
      const usuarios = await listarUsuarios(empresa.id)
      const vinculo = usuarios.find(u => u.email.toLowerCase() === email.value.toLowerCase()) ?? null
      nuevasFilas.push({
        empresa,
        vinculo,
        rolSeleccionado: vinculo && vinculo.activo ? vinculo.rol : 'sin_acceso'
      })
    }
    filas.value = nuevasFilas
    buscado.value = true
  } catch (error) {
    toast.add({ title: 'No se pudo buscar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    buscando.value = false
  }
}

async function cambiarRol(fila: Fila, nuevoRol: string) {
  actualizandoEmpresaId.value = fila.empresa.id
  try {
    if (nuevoRol === 'sin_acceso') {
      if (fila.vinculo && fila.vinculo.activo) {
        await actualizar(fila.empresa.id, fila.vinculo.id, { activo: false })
      }
    } else if (!fila.vinculo) {
      await agregar(fila.empresa.id, { email: email.value, rol: nuevoRol })
    } else {
      await actualizar(fila.empresa.id, fila.vinculo.id, { rol: nuevoRol, activo: true })
    }
    const usuarios = await listarUsuarios(fila.empresa.id)
    fila.vinculo = usuarios.find(u => u.email.toLowerCase() === email.value.toLowerCase()) ?? null
    fila.rolSeleccionado = fila.vinculo && fila.vinculo.activo ? fila.vinculo.rol : 'sin_acceso'
    toast.add({ title: 'Acceso actualizado', color: 'success' })
  } catch (error) {
    toast.add({ title: 'No se pudo actualizar el acceso', description: extraerMensajeError(error), color: 'error' })
    fila.rolSeleccionado = fila.vinculo && fila.vinculo.activo ? fila.vinculo.rol : 'sin_acceso'
  } finally {
    actualizandoEmpresaId.value = null
  }
}
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-1">
      Accesos entre mis empresas
    </h1>
    <p class="text-sm text-gray-500 mb-4">
      Da o quita, para un usuario que ya existe, acceso de contador o consulta en las empresas donde sos admin -- sin cambiar de empresa activa por cada una.
    </p>

    <UCard class="mb-4">
      <div class="flex items-end gap-3">
        <UFormField
          label="Email del usuario"
          class="flex-1"
        >
          <UInput
            v-model="email"
            type="email"
            class="w-full"
            placeholder="usuario@ejemplo.com"
            @keyup.enter="buscar"
          />
        </UFormField>
        <UButton
          :loading="buscando"
          :disabled="!email"
          @click="buscar"
        >
          Buscar
        </UButton>
      </div>
    </UCard>

    <UCard v-if="buscado">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Empresa
            </th>
            <th class="py-2">
              Acceso
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="fila in filas"
            :key="fila.empresa.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ fila.empresa.nombre_comercial || fila.empresa.razon_social }}
            </td>
            <td class="py-2">
              <USelect
                :model-value="fila.rolSeleccionado"
                :items="opcionesRol"
                value-key="value"
                size="sm"
                :disabled="actualizandoEmpresaId === fila.empresa.id"
                class="w-40"
                @update:model-value="(rol: string) => cambiarRol(fila, rol)"
              />
            </td>
          </tr>
          <tr v-if="filas.length === 0">
            <td
              colspan="2"
              class="py-8 text-center text-gray-500"
            >
              No administrás ninguna empresa todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

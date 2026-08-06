<script setup lang="ts">
import type { Empleado } from '~/composables/useEmpleados'

const { listar } = useEmpleados()
const { data: empleados, pending, refresh } = await useAsyncData<Empleado[]>('empleados', () => listar())

const busqueda = ref('')
const filtrados = computed(() => {
  const q = busqueda.value.trim().toLowerCase()
  if (!q) return empleados.value ?? []
  return (empleados.value ?? []).filter(e =>
    e.nombre_completo.toLowerCase().includes(q) || e.identificacion.toLowerCase().includes(q)
  )
})

onActivated(() => refresh())
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
        Empleados
      </h1>
      <UButton
        icon="i-lucide-plus"
        to="/empleados/nuevo"
      >
        Nuevo empleado
      </UButton>
    </div>

    <UInput
      v-model="busqueda"
      icon="i-lucide-search"
      placeholder="Buscar por nombre o identificación"
      class="mb-4 max-w-sm"
    />

    <UCard>
      <div
        v-if="pending"
        class="text-center py-8 text-gray-500"
      >
        Cargando...
      </div>
      <table
        v-else
        class="w-full text-sm"
      >
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Nombre
            </th>
            <th class="py-2 pr-4">
              Identificación
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="empleado in filtrados"
            :key="empleado.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ empleado.nombre_completo }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ empleado.identificacion }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="empleado.estado === 'activo' ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ empleado.estado }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-chevron-right"
                :to="`/empleados/${empleado.id}`"
              />
            </td>
          </tr>
          <tr v-if="filtrados.length === 0">
            <td
              colspan="4"
              class="py-8 text-center text-gray-500"
            >
              Sin resultados.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

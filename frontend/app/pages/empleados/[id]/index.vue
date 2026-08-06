<script setup lang="ts">
const route = useRoute()
const empleadoId = route.params.id as string

const { obtener } = useEmpleados()
const { listarDeEmpleado } = useContratos()

const { data: empleado } = await useAsyncData(`empleado-${empleadoId}`, () => obtener(empleadoId))
const { data: contratos, refresh: refrescarContratos } = await useAsyncData(
  `contratos-${empleadoId}`, () => listarDeEmpleado(empleadoId)
)

onActivated(() => refrescarContratos())
</script>

<template>
  <div v-if="empleado">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ empleado.nombre_completo }}
        </h1>
        <p class="text-sm text-gray-500">
          {{ empleado.identificacion }} · {{ empleado.tipo_identificacion }}
        </p>
      </div>
      <UBadge
        :color="empleado.estado === 'activo' ? 'success' : 'neutral'"
        variant="subtle"
      >
        {{ empleado.estado }}
      </UBadge>
    </div>

    <UCard class="mb-6">
      <template #header>
        <span class="font-medium">Datos personales</span>
      </template>
      <dl class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <dt class="text-gray-500">
            Email personal
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.email_personal || '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Teléfono
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.telefono || '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Dirección
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.direccion || '—' }}
          </dd>
        </div>
      </dl>
    </UCard>

    <div class="flex items-center justify-between mb-3">
      <h2 class="font-medium text-gray-900 dark:text-white">
        Contratos
      </h2>
      <UButton
        size="sm"
        icon="i-lucide-plus"
        :to="`/empleados/${empleadoId}/contratos/nuevo`"
      >
        Nuevo contrato
      </UButton>
    </div>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Cargo
            </th>
            <th class="py-2 pr-4">
              Tipo
            </th>
            <th class="py-2 pr-4">
              Inicio
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="contrato in contratos"
            :key="contrato.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ contrato.cargo }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ contrato.tipo_contrato }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ formatearFecha(contrato.fecha_inicio) }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="contrato.estado === 'vigente' ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ contrato.estado }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-chevron-right"
                :to="`/empleados/${empleadoId}/contratos/${contrato.id}`"
              />
            </td>
          </tr>
          <tr v-if="!contratos || contratos.length === 0">
            <td
              colspan="5"
              class="py-8 text-center text-gray-500"
            >
              Sin contratos todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

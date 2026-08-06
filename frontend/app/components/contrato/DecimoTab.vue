<script setup lang="ts">
const props = defineProps<{ contratoId: string }>()

const { provisiones } = useDecimo()
const { data: provs } = await useAsyncData(`decimo-${props.contratoId}`, () => provisiones(props.contratoId))
</script>

<template>
  <UCard>
    <template #header>
      <span class="font-medium">Provisiones de décimo tercer mes</span>
    </template>
    <p class="text-sm text-gray-500 mb-4">
      Los pagos de décimo se generan por cuatrimestre para toda la empresa desde
      <NuxtLink
        to="/planillas/generar-decimo"
        class="text-primary underline"
      >Planillas → Generar décimo</NuxtLink>.
    </p>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
          <th class="py-2 pr-4">
            Cuatrimestre
          </th>
          <th class="py-2 pr-4">
            Año
          </th>
          <th class="py-2 pr-4">
            Monto acumulado
          </th>
          <th class="py-2 pr-4">
            Fecha de pago programada
          </th>
          <th class="py-2">
            Estado
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="p in provs"
          :key="p.id"
          class="border-b border-gray-100 dark:border-gray-800 last:border-0"
        >
          <td class="py-2 pr-4">
            {{ p.cuatrimestre }}
          </td>
          <td class="py-2 pr-4">
            {{ p.anio }}
          </td>
          <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
            ${{ p.monto_acumulado }}
          </td>
          <td class="py-2 pr-4">
            {{ formatearFecha(p.fecha_pago_programada) }}
          </td>
          <td class="py-2">
            <UBadge
              :color="p.pagado ? 'success' : 'warning'"
              variant="subtle"
            >
              {{ p.pagado ? 'Pagado' : 'Pendiente' }}
            </UBadge>
          </td>
        </tr>
        <tr v-if="!provs || provs.length === 0">
          <td
            colspan="5"
            class="py-8 text-center text-gray-500"
          >
            Sin provisiones todavía.
          </td>
        </tr>
      </tbody>
    </table>
  </UCard>
</template>

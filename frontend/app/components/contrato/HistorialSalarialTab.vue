<script setup lang="ts">
const props = defineProps<{ contratoId: string }>()

const { historialSalarial } = useContratos()
const { data: historial } = await useAsyncData(`historial-${props.contratoId}`, () => historialSalarial(props.contratoId))
</script>

<template>
  <UCard>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
          <th class="py-2 pr-4">
            Salario base
          </th>
          <th class="py-2 pr-4">
            Vigente desde
          </th>
          <th class="py-2 pr-4">
            Vigente hasta
          </th>
          <th class="py-2">
            Motivo
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="h in historial"
          :key="h.id"
          class="border-b border-gray-100 dark:border-gray-800 last:border-0"
        >
          <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
            ${{ h.salario_base }}
          </td>
          <td class="py-2 pr-4">
            {{ formatearFecha(h.fecha_vigencia_desde) }}
          </td>
          <td class="py-2 pr-4">
            {{ formatearFecha(h.fecha_vigencia_hasta, 'Vigente') }}
          </td>
          <td class="py-2 text-gray-500">
            {{ h.motivo || '—' }}
          </td>
        </tr>
        <tr v-if="!historial || historial.length === 0">
          <td
            colspan="4"
            class="py-8 text-center text-gray-500"
          >
            Sin historial.
          </td>
        </tr>
      </tbody>
    </table>
  </UCard>
</template>

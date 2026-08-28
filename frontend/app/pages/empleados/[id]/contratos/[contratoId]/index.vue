<script setup lang="ts">
const route = useRoute()
const empleadoId = route.params.id as string
const contratoId = route.params.contratoId as string

const { obtener } = useContratos()
const { data: contrato, refresh: refrescarContrato } = await useAsyncData(`contrato-${contratoId}`, () => obtener(contratoId))

const tabs = [
  { value: 'resumen', label: 'Resumen' },
  { value: 'historial', label: 'Historial salarial' },
  { value: 'horas-extra', label: 'Horas extra' },
  { value: 'conceptos', label: 'Conceptos variables' },
  { value: 'decimo', label: 'Décimo' },
  { value: 'vacaciones', label: 'Vacaciones' },
  { value: 'ausencias', label: 'Ausencias' },
  { value: 'liquidacion', label: 'Liquidación' }
]
const tabActivo = ref((route.query.tab as string) || 'resumen')
</script>

<template>
  <div v-if="contrato">
    <div class="mb-4">
      <NuxtLink
        v-if="tabActivo !== 'liquidacion'"
        :to="`/empleados/${empleadoId}`"
        class="text-sm text-gray-500 hover:text-primary flex items-center gap-1"
      >
        <UIcon name="i-lucide-arrow-left" /> Volver al empleado
      </NuxtLink>
      <button
        v-else
        type="button"
        class="text-sm text-gray-500 hover:text-primary flex items-center gap-1"
        @click="tabActivo = 'resumen'"
      >
        <UIcon name="i-lucide-arrow-left" /> Volver al contrato
      </button>
      <div class="flex items-center gap-3 mt-1">
        <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ contrato.cargo }}
        </h1>
        <UBadge
          :color="contrato.estado === 'vigente' ? 'success' : 'neutral'"
          variant="subtle"
        >
          {{ contrato.estado }}
        </UBadge>
      </div>
    </div>

    <div class="flex gap-1 border-b border-gray-200 dark:border-gray-800 mb-6 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        class="px-3 py-2 text-sm whitespace-nowrap border-b-2 -mb-px transition-colors"
        :class="tabActivo === tab.value
          ? 'border-primary text-primary font-medium'
          : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-white'"
        @click="tabActivo = tab.value"
      >
        {{ tab.label }}
      </button>
    </div>

    <ContratoResumenTab
      v-if="tabActivo === 'resumen'"
      :contrato="contrato"
      @contrato-actualizado="refrescarContrato"
    />
    <ContratoHistorialSalarialTab
      v-else-if="tabActivo === 'historial'"
      :contrato-id="contratoId"
    />
    <ContratoHorasExtraTab
      v-else-if="tabActivo === 'horas-extra'"
      :contrato-id="contratoId"
    />
    <ContratoConceptosVariablesTab
      v-else-if="tabActivo === 'conceptos'"
      :contrato-id="contratoId"
    />
    <ContratoDecimoTab
      v-else-if="tabActivo === 'decimo'"
      :contrato-id="contratoId"
    />
    <ContratoVacacionesTab
      v-else-if="tabActivo === 'vacaciones'"
      :contrato-id="contratoId"
    />
    <ContratoAusenciasTab
      v-else-if="tabActivo === 'ausencias'"
      :contrato-id="contratoId"
    />
    <ContratoLiquidacionTab
      v-else-if="tabActivo === 'liquidacion'"
      :contrato="contrato"
      @contrato-actualizado="refrescarContrato"
    />
  </div>
</template>

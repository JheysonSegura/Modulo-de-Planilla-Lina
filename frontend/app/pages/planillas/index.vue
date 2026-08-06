<script setup lang="ts">
import type { Planilla } from '~/composables/usePlanillas'

const { listar } = usePlanillas()

const filtroTipo = ref<string | undefined>(undefined)
const filtroEstado = ref<string | undefined>(undefined)

const { data: planillas, pending, refresh } = await useAsyncData<Planilla[]>(
  'planillas', () => listar(filtroTipo.value, filtroEstado.value), { watch: [filtroTipo, filtroEstado] }
)

const opcionesTipo = [
  { label: 'Todos', value: undefined },
  { label: 'Mensual', value: 'mensual' },
  { label: 'Quincenal', value: 'quincenal' },
  { label: 'Décimo tercer mes', value: 'decimo_tercer_mes' }
]
const opcionesEstado = [
  { label: 'Todos', value: undefined },
  { label: 'Borrador', value: 'borrador' },
  { label: 'Procesada', value: 'procesada' },
  { label: 'Pagada', value: 'pagada' },
  { label: 'Anulada', value: 'anulada' }
]

const colorEstado: Record<string, 'neutral' | 'success' | 'warning' | 'error'> = {
  borrador: 'warning', procesada: 'success', pagada: 'success', anulada: 'error'
}

onActivated(() => refresh())
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
        Planillas
      </h1>
      <div class="flex gap-2">
        <UButton
          color="neutral"
          variant="soft"
          icon="i-lucide-gift"
          to="/planillas/generar-decimo"
        >
          Generar décimo
        </UButton>
        <UButton
          icon="i-lucide-plus"
          to="/planillas/nueva"
        >
          Nueva planilla
        </UButton>
      </div>
    </div>

    <div class="flex gap-3 mb-4">
      <USelect
        v-model="filtroTipo"
        :items="opcionesTipo"
        value-key="value"
        placeholder="Tipo"
        class="w-48"
      />
      <USelect
        v-model="filtroEstado"
        :items="opcionesEstado"
        value-key="value"
        placeholder="Estado"
        class="w-48"
      />
    </div>

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
              Tipo
            </th>
            <th class="py-2 pr-4">
              Período
            </th>
            <th class="py-2 pr-4">
              Fecha de pago
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in planillas"
            :key="p.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ p.tipo }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(p.periodo_inicio) }} — {{ formatearFecha(p.periodo_fin) }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(p.fecha_pago) }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="colorEstado[p.estado]"
                variant="subtle"
              >
                {{ p.estado }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-chevron-right"
                :to="`/planillas/${p.id}`"
              />
            </td>
          </tr>
          <tr v-if="!planillas || planillas.length === 0">
            <td
              colspan="5"
              class="py-8 text-center text-gray-500"
            >
              Sin planillas todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

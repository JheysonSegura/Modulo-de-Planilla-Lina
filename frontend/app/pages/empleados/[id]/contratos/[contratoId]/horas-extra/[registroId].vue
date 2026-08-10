<script setup lang="ts">
const route = useRoute()
const empleadoId = route.params.id as string
const contratoId = route.params.contratoId as string
const registroId = route.params.registroId as string

const { listar } = useHorasExtra()
const { data: registros } = await useAsyncData(`horas-extra-detalle-${contratoId}`, () => listar(contratoId))
const registro = computed(() => registros.value?.find(r => r.id === registroId))

const etiquetasTipoHora: Record<string, string> = {
  diurna: 'Diurna',
  nocturna: 'Nocturna',
  prolongacion_nocturna: 'Prolongación nocturna'
}
const etiquetasTipoDia: Record<string, string> = {
  ordinario: 'Ordinario',
  domingo_descanso: 'Domingo/descanso',
  feriado_duelo_nacional: 'Feriado/duelo nacional'
}

function formatearPorcentaje(valor: string): string {
  return `+${(Number(valor) * 100).toFixed(2)}%`
}

const hayExceso = computed(() => Number(registro.value?.horas_exceso_limite ?? '0') > 0)
</script>

<template>
  <div v-if="registro">
    <div class="mb-4">
      <NuxtLink
        :to="`/empleados/${empleadoId}/contratos/${contratoId}`"
        class="text-sm text-gray-500 hover:text-primary flex items-center gap-1"
      >
        <UIcon name="i-lucide-arrow-left" /> Volver al contrato
      </NuxtLink>
      <h1 class="text-xl font-semibold text-gray-900 dark:text-white mt-1">
        Desglose de hora extra — {{ formatearFecha(registro.fecha) }}
      </h1>
    </div>

    <div class="space-y-4">
      <UCard>
        <template #header>
          <h2 class="font-medium">
            Datos del registro
          </h2>
        </template>
        <dl class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <dt class="text-gray-500">
              Fecha
            </dt>
            <dd class="font-medium">
              {{ formatearFecha(registro.fecha) }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Tipo de hora
            </dt>
            <dd class="font-medium">
              {{ etiquetasTipoHora[registro.tipo_hora] }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Tipo de día
            </dt>
            <dd class="font-medium">
              {{ etiquetasTipoDia[registro.tipo_dia] }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Horas registradas
            </dt>
            <dd class="font-medium">
              {{ registro.horas }}
            </dd>
          </div>
        </dl>
        <p
          v-if="registro.observaciones"
          class="text-sm text-gray-500 mt-4"
        >
          Observaciones: {{ registro.observaciones }}
        </p>
      </UCard>

      <UCard>
        <template #header>
          <h2 class="font-medium">
            Cómo se calculó el monto a pagar
          </h2>
        </template>
        <div class="space-y-6 text-sm">
          <div>
            <p class="text-gray-500 mb-1">
              1. Valor de la hora ordinaria (salario mensual vigente ÷ 30 días ÷ 8 horas)
            </p>
            <p class="font-medium">
              ${{ registro.valor_hora_ordinaria }} / hora
            </p>
          </div>

          <div>
            <p class="text-gray-500 mb-1">
              2. Reparto de horas según los topes legales (Art. 36 CT: máx. 3h extra/día, 9h/semana)
            </p>
            <p class="font-medium">
              {{ registro.horas_dentro_limite }} horas dentro del límite
              <template v-if="hayExceso">
                + {{ registro.horas_exceso_limite }} horas en exceso del límite
              </template>
            </p>
          </div>

          <div>
            <p class="text-gray-500 mb-1">
              3. Recargos aplicados en cascada (multiplicativos, nunca sumados)
            </p>
            <ul class="list-disc list-inside font-medium space-y-0.5">
              <li>Por tipo de hora ({{ etiquetasTipoHora[registro.tipo_hora] }}): {{ formatearPorcentaje(registro.factor_tipo_hora) }}</li>
              <li>Por tipo de día ({{ etiquetasTipoDia[registro.tipo_dia] }}): {{ formatearPorcentaje(registro.factor_tipo_dia) }}</li>
              <li v-if="hayExceso">
                Recargo adicional por exceder el límite legal: {{ formatearPorcentaje(registro.factor_exceso_limite) }}
              </li>
            </ul>
          </div>

          <div class="border-t border-gray-200 dark:border-gray-800 pt-4">
            <p class="text-gray-500 mb-1">
              4. Monto dentro del límite
            </p>
            <p class="font-mono text-xs text-gray-500">
              {{ registro.horas_dentro_limite }} h × ${{ registro.valor_hora_ordinaria }} × (1 {{ formatearPorcentaje(registro.factor_tipo_hora) }}) × (1 {{ formatearPorcentaje(registro.factor_tipo_dia) }})
            </p>
            <p class="font-medium mt-1">
              = ${{ registro.monto_dentro_limite }}
            </p>
          </div>

          <div
            v-if="hayExceso"
            class="border-t border-gray-200 dark:border-gray-800 pt-4"
          >
            <p class="text-gray-500 mb-1">
              5. Monto en exceso del límite (recargo adicional)
            </p>
            <p class="font-mono text-xs text-gray-500">
              {{ registro.horas_exceso_limite }} h × ${{ registro.valor_hora_ordinaria }} × (1 {{ formatearPorcentaje(registro.factor_tipo_hora) }}) × (1 {{ formatearPorcentaje(registro.factor_tipo_dia) }}) × (1 {{ formatearPorcentaje(registro.factor_exceso_limite) }})
            </p>
            <p class="font-medium mt-1">
              = ${{ registro.monto_exceso_limite }}
            </p>
          </div>

          <div class="border-t-2 border-gray-300 dark:border-gray-700 pt-4">
            <p class="text-gray-500 mb-1">
              Total a pagar por esta hora extra
            </p>
            <p class="text-lg font-semibold text-gray-900 dark:text-white">
              ${{ registro.monto_calculado }}
            </p>
          </div>
        </div>
      </UCard>
    </div>
  </div>
  <div
    v-else
    class="text-center text-gray-500 py-12"
  >
    Registro no encontrado.
  </div>
</template>

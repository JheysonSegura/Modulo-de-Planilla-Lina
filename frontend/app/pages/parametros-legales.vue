<script setup lang="ts">
const { vigentes, isr, riesgoProfesional, salarioMinimo } = useTasas()

const { data: tasas } = await useAsyncData('tasas-vigentes', () => vigentes())
const { data: tramos } = await useAsyncData('tasas-isr', () => isr())
const { data: riesgo } = await useAsyncData('tasas-riesgo', () => riesgoProfesional())

const busquedaSalarioMinimo = ref('')
const { data: minimos, refresh: refrescarMinimos } = await useAsyncData(
  'salario-minimo', () => salarioMinimo(undefined, busquedaSalarioMinimo.value || undefined)
)

const etiquetasTasas: Record<string, string> = {
  css_empleado: 'CSS — cuota obrero',
  css_patronal: 'CSS — cuota patronal',
  seguro_educativo_empleado: 'Seguro Educativo — empleado',
  seguro_educativo_patronal: 'Seguro Educativo — patronal',
  decimo_empleado: 'CSS especial sobre décimo — empleado',
  decimo_patronal: 'CSS especial sobre décimo — patronal'
}

function formatearPorcentaje(tasa: string) {
  return `${(Number(tasa) * 100).toFixed(2)}%`
}

let temporizador: ReturnType<typeof setTimeout> | undefined
watch(busquedaSalarioMinimo, () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(() => refrescarMinimos(), 400)
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
      Parámetros legales vigentes
    </h1>

    <UCard>
      <template #header>
        <span class="font-medium">CSS, Seguro Educativo y cuota especial sobre décimo</span>
      </template>
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="t in tasas"
            :key="t.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ etiquetasTasas[t.tipo_tasa] || t.tipo_tasa }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ formatearPorcentaje(t.tasa) }}
            </td>
            <td class="py-2 text-gray-500 text-xs">
              {{ t.fuente_legal }}
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>

    <UCard>
      <template #header>
        <span class="font-medium">Tabla progresiva de ISR</span>
      </template>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Desde
            </th>
            <th class="py-2 pr-4">
              Hasta
            </th>
            <th class="py-2 pr-4">
              Tasa marginal
            </th>
            <th class="py-2">
              Base acumulada
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in tramos"
            :key="t.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              ${{ t.monto_desde }}
            </td>
            <td class="py-2 pr-4">
              {{ t.monto_hasta ? `$${t.monto_hasta}` : 'Sin límite' }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ formatearPorcentaje(t.tasa_marginal) }}
            </td>
            <td class="py-2">
              ${{ t.impuesto_base }}
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>

    <UCard>
      <template #header>
        <span class="font-medium">Riesgo profesional por clase (I-V)</span>
      </template>
      <p class="text-xs text-gray-500 mb-3">
        ⚠️ Cifras sembradas como interpretación del Decreto de Gabinete N.68/1970, aún sin confirmar con un aviso real de la CSS.
      </p>
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="r in riesgo"
            :key="r.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              Clase {{ r.clase_riesgo }}
            </td>
            <td class="py-2 font-medium text-gray-900 dark:text-white">
              {{ formatearPorcentaje(r.tasa) }}
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>

    <UCard>
      <template #header>
        <span class="font-medium">Salario mínimo (Decreto Ejecutivo N.13)</span>
      </template>
      <UInput
        v-model="busquedaSalarioMinimo"
        icon="i-lucide-search"
        placeholder="Buscar por actividad"
        class="mb-3 max-w-sm"
      />
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Región
            </th>
            <th class="py-2 pr-4">
              Actividad
            </th>
            <th class="py-2 pr-4">
              Tamaño
            </th>
            <th class="py-2 pr-4">
              Por hora
            </th>
            <th class="py-2">
              Mensual
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in minimos"
            :key="m.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ m.region }}
            </td>
            <td class="py-2 pr-4">
              {{ m.actividad || 'General' }}
            </td>
            <td class="py-2 pr-4">
              {{ m.tamano_empresa || '—' }}
            </td>
            <td class="py-2 pr-4">
              {{ m.monto_hora ? `$${m.monto_hora}` : '—' }}
            </td>
            <td class="py-2">
              {{ m.monto_mensual ? `$${m.monto_mensual}` : '—' }}
            </td>
          </tr>
          <tr v-if="!minimos || minimos.length === 0">
            <td
              colspan="5"
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

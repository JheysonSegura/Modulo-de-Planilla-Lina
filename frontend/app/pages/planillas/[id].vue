<script setup lang="ts">
const route = useRoute()
const planillaId = route.params.id as string

const { obtener, movimientos, aprobar } = usePlanillas()
const { obtener: obtenerContrato } = useContratos()
const { obtener: obtenerEmpleado } = useEmpleados()
const { descargar } = useReportes()
const toast = useToast()

const { data: planilla, refresh: refrescarPlanilla } = await useAsyncData(`planilla-${planillaId}`, () => obtener(planillaId))
const { data: movs } = await useAsyncData(`planilla-movimientos-${planillaId}`, () => movimientos(planillaId))

const nombresPorContrato = ref<Record<string, string>>({})

async function cargarNombres() {
  if (!movs.value) return
  const contratoIds = [...new Set(movs.value.map(m => m.contrato_id))]
  for (const contratoId of contratoIds) {
    try {
      const contrato = await obtenerContrato(contratoId)
      const empleado = await obtenerEmpleado(contrato.empleado_id)
      nombresPorContrato.value[contratoId] = empleado.nombre_completo
    } catch {
      nombresPorContrato.value[contratoId] = contratoId
    }
  }
}
await cargarNombres()

const aprobando = ref(false)
async function aprobarPlanilla() {
  aprobando.value = true
  try {
    await aprobar(planillaId)
    toast.add({ title: 'Planilla aprobada', color: 'success' })
    await refrescarPlanilla()
  } catch (error) {
    toast.add({ title: 'No se pudo aprobar', description: String(error), color: 'error' })
  } finally {
    aprobando.value = false
  }
}

const totalNeto = computed(() =>
  (movs.value ?? []).reduce((acc, m) => acc + Number(m.salario_neto), 0).toFixed(2)
)

async function descargarBoleta(movimientoId: string, contratoId: string, formato: 'pdf' | 'excel') {
  const nombre = nombresPorContrato.value[contratoId] || contratoId
  const extension = formato === 'pdf' ? 'pdf' : 'xlsx'
  try {
    await descargar(
      `/planillas/${planillaId}/movimientos/${movimientoId}/boleta`,
      { formato },
      `boleta-pago-${nombre}-${planilla.value?.periodo_fin}.${extension}`
    )
  } catch (error) {
    toast.add({ title: 'No se pudo descargar la boleta', description: String(error), color: 'error' })
  }
}

const exportando = ref(false)
async function exportarPlanilla(formato: 'excel' | 'csv') {
  exportando.value = true
  const extension = formato === 'excel' ? 'xlsx' : 'csv'
  try {
    await descargar(
      `/planillas/${planillaId}/exportar`,
      { formato },
      `planilla-${planilla.value?.tipo}-${planilla.value?.periodo_inicio}-${planilla.value?.periodo_fin}.${extension}`
    )
  } catch (error) {
    toast.add({ title: 'No se pudo exportar la planilla', description: String(error), color: 'error' })
  } finally {
    exportando.value = false
  }
}
</script>

<template>
  <div v-if="planilla">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-white capitalize">
          {{ planilla.tipo.replace(/_/g, ' ') }}
        </h1>
        <p class="text-sm text-gray-500">
          {{ formatearFecha(planilla.periodo_inicio) }} — {{ formatearFecha(planilla.periodo_fin) }} · Pago: {{ formatearFecha(planilla.fecha_pago) }}
        </p>
      </div>
      <div class="flex items-center gap-3">
        <UBadge variant="subtle">
          {{ planilla.estado }}
        </UBadge>
        <UButton
          size="xs"
          variant="soft"
          color="neutral"
          icon="i-lucide-file-spreadsheet"
          :loading="exportando"
          @click="exportarPlanilla('excel')"
        >
          Excel
        </UButton>
        <UButton
          size="xs"
          variant="soft"
          color="neutral"
          icon="i-lucide-file-text"
          :loading="exportando"
          @click="exportarPlanilla('csv')"
        >
          CSV
        </UButton>
        <UButton
          v-if="planilla.estado === 'borrador'"
          :loading="aprobando"
          icon="i-lucide-check"
          @click="aprobarPlanilla"
        >
          Aprobar
        </UButton>
      </div>
    </div>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Empleado
            </th>
            <th class="py-2 pr-4">
              Salario bruto
            </th>
            <th class="py-2 pr-4">
              CSS empl.
            </th>
            <th class="py-2 pr-4">
              S.E. empl.
            </th>
            <th class="py-2 pr-4">
              ISR
            </th>
            <th class="py-2 pr-4">
              Otras ded.
            </th>
            <th class="py-2 pr-4">
              Neto
            </th>
            <th class="py-2">
              Boleta
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in movs"
            :key="m.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ nombresPorContrato[m.contrato_id] || m.contrato_id }}
            </td>
            <td class="py-2 pr-4">
              ${{ m.salario_bruto }}
            </td>
            <td class="py-2 pr-4 text-error">
              -${{ m.css_empleado }}
            </td>
            <td class="py-2 pr-4 text-error">
              -${{ m.seguro_educativo_empleado }}
            </td>
            <td class="py-2 pr-4 text-error">
              -${{ m.isr_retenido }}
            </td>
            <td class="py-2 pr-4 text-error">
              -${{ m.otras_deducciones }}
            </td>
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              ${{ m.salario_neto }}
            </td>
            <td class="py-2">
              <div class="flex gap-1">
                <UButton
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-file-text"
                  title="Descargar PDF"
                  @click="descargarBoleta(m.id, m.contrato_id, 'pdf')"
                />
                <UButton
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-file-spreadsheet"
                  title="Descargar Excel"
                  @click="descargarBoleta(m.id, m.contrato_id, 'excel')"
                />
              </div>
            </td>
          </tr>
          <tr v-if="!movs || movs.length === 0">
            <td
              colspan="8"
              class="py-8 text-center text-gray-500"
            >
              Sin movimientos.
            </td>
          </tr>
        </tbody>
        <tfoot v-if="movs && movs.length > 0">
          <tr class="border-t-2 border-gray-300 dark:border-gray-700 font-semibold text-gray-900 dark:text-white">
            <td
              class="py-2 pr-4"
              colspan="6"
            >
              Total neto
            </td>
            <td
              class="py-2"
              colspan="2"
            >
              ${{ totalNeto }}
            </td>
          </tr>
        </tfoot>
      </table>
    </UCard>
  </div>
</template>

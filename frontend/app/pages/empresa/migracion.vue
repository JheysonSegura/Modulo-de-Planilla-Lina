<script setup lang="ts">
const { disponible, descargarPlantilla, validar, confirmar } = useMigracionDatos()
const toast = useToast()

const paso = ref<'preparar' | 'revisar' | 'confirmado'>('preparar')
const fechaCorte = ref('')
const archivoSeleccionado = ref<File | null>(null)
const inputArchivo = ref<HTMLInputElement>()

const cargandoDisponible = ref(true)
const disponibleInfo = ref<{ disponible: boolean, motivo?: string | null } | null>(null)

const cargandoValidar = ref(false)
const errores = ref<ErrorValidacionMigracion[]>([])
const resumen = ref<ResumenMigracion | null>(null)
const cargandoConfirmar = ref(false)
const resumenFinal = ref<ResumenMigracion | null>(null)

onMounted(async () => {
  try {
    disponibleInfo.value = await disponible()
  } catch (error) {
    toast.add({ title: 'No se pudo verificar la disponibilidad', description: extraerMensajeError(error), color: 'error' })
  } finally {
    cargandoDisponible.value = false
  }
})

const avisoFechaCorte = computed(() => {
  if (!fechaCorte.value) return null
  const dia = new Date(`${fechaCorte.value}T00:00:00`).getUTCDate()
  if (dia !== 1 && dia !== 16) {
    return 'La fecha de corte normalmente cae el día 1 o 16 de un mes (inicio de un período de planilla). Podés continuar igual si estás seguro.'
  }
  return null
})

function onSeleccionarArchivo(event: Event) {
  archivoSeleccionado.value = (event.target as HTMLInputElement).files?.[0] ?? null
  errores.value = []
  resumen.value = null
}

async function onDescargarPlantilla() {
  try {
    await descargarPlantilla()
  } catch (error) {
    toast.add({ title: 'No se pudo descargar la plantilla', description: extraerMensajeError(error), color: 'error' })
  }
}

async function onValidar() {
  if (!fechaCorte.value || !archivoSeleccionado.value) return
  cargandoValidar.value = true
  errores.value = []
  resumen.value = null
  try {
    const resultado = await validar(archivoSeleccionado.value, fechaCorte.value)
    if (resultado.errores.length > 0) {
      errores.value = resultado.errores
    } else {
      resumen.value = resultado.resumen
      paso.value = 'revisar'
    }
  } catch (error) {
    toast.add({ title: 'No se pudo validar el archivo', description: extraerMensajeError(error), color: 'error' })
  } finally {
    cargandoValidar.value = false
  }
}

function volverAEditar() {
  paso.value = 'preparar'
}

async function onConfirmar() {
  if (!fechaCorte.value || !archivoSeleccionado.value) return
  cargandoConfirmar.value = true
  try {
    const resultado = await confirmar(archivoSeleccionado.value, fechaCorte.value)
    resumenFinal.value = resultado.resumen
    paso.value = 'confirmado'
  } catch (error) {
    toast.add({ title: 'No se pudo confirmar la migración', description: extraerMensajeError(error), color: 'error' })
  } finally {
    cargandoConfirmar.value = false
  }
}
</script>

<template>
  <div class="max-w-3xl">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-1">
      Importar datos de otro sistema
    </h1>
    <p class="text-sm text-gray-500 mb-4">
      Asistente para cargar empleados, contratos y saldos de una empresa que viene de otro sistema (Excel, otro software, etc.), solo disponible mientras esta empresa todavía no tiene datos operativos.
    </p>

    <UAlert
      v-if="!cargandoDisponible && disponibleInfo && !disponibleInfo.disponible"
      color="warning"
      variant="subtle"
      title="No disponible"
      :description="disponibleInfo.motivo || 'Esta empresa ya no puede usar el asistente de migración.'"
      class="mb-4"
    />

    <template v-if="cargandoDisponible">
      <p class="text-gray-500">
        Verificando...
      </p>
    </template>

    <template v-else-if="disponibleInfo?.disponible">
      <UCard
        v-if="paso === 'preparar'"
        class="mb-4"
      >
        <div class="space-y-4">
          <UFormField
            label="Fecha de corte"
            help="Fecha desde la que este sistema empieza a llevar la nómina -- debe ser el inicio de un período de planilla."
          >
            <UInput
              v-model="fechaCorte"
              type="date"
              class="w-full max-w-xs"
            />
          </UFormField>
          <UAlert
            v-if="avisoFechaCorte"
            color="warning"
            variant="subtle"
            :description="avisoFechaCorte"
          />

          <div>
            <p class="text-sm text-gray-500 mb-2">
              1. Descargá la plantilla y completá al menos la hoja "Empleados y contratos" (obligatoria). Las demás hojas son opcionales -- la plantilla trae instrucciones de qué pasa si se dejan vacías.
            </p>
            <UButton
              color="neutral"
              variant="soft"
              icon="i-lucide-download"
              @click="onDescargarPlantilla"
            >
              Descargar plantilla
            </UButton>
          </div>

          <div>
            <p class="text-sm text-gray-500 mb-2">
              2. Subí la plantilla ya completada.
            </p>
            <UButton
              variant="soft"
              color="neutral"
              icon="i-lucide-paperclip"
              @click="inputArchivo?.click()"
            >
              {{ archivoSeleccionado ? archivoSeleccionado.name : 'Seleccionar archivo' }}
            </UButton>
            <input
              ref="inputArchivo"
              type="file"
              accept=".xlsx"
              class="hidden"
              @change="onSeleccionarArchivo"
            >
          </div>

          <UButton
            :loading="cargandoValidar"
            :disabled="!fechaCorte || !archivoSeleccionado"
            @click="onValidar"
          >
            Validar
          </UButton>
        </div>
      </UCard>

      <UCard
        v-if="paso === 'preparar' && errores.length > 0"
        class="mb-4"
      >
        <p class="text-sm font-medium text-red-600 dark:text-red-400 mb-3">
          {{ errores.length }} error(es) encontrados -- corregí el archivo y volvé a subirlo.
        </p>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
              <th class="py-2 pr-4">
                Hoja
              </th>
              <th class="py-2 pr-4">
                Fila
              </th>
              <th class="py-2 pr-4">
                Campo
              </th>
              <th class="py-2">
                Error
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(e, i) in errores"
              :key="i"
              class="border-b border-gray-100 dark:border-gray-800 last:border-0"
            >
              <td class="py-2 pr-4">
                {{ e.hoja }}
              </td>
              <td class="py-2 pr-4">
                {{ e.fila }}
              </td>
              <td class="py-2 pr-4 text-gray-500">
                {{ e.campo || '-' }}
              </td>
              <td class="py-2">
                {{ e.mensaje }}
              </td>
            </tr>
          </tbody>
        </table>
      </UCard>

      <UCard v-if="paso === 'revisar' && resumen">
        <p class="text-sm text-gray-500 mb-3">
          Sin errores. Revisá el resumen antes de confirmar -- esta acción no se puede deshacer.
        </p>
        <dl class="grid grid-cols-2 gap-3 text-sm mb-4">
          <div>
            <dt class="text-gray-500">
              Empleados a crear
            </dt>
            <dd class="font-medium text-gray-900 dark:text-white">
              {{ resumen.empleados }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Tramos de salario adicionales
            </dt>
            <dd class="font-medium text-gray-900 dark:text-white">
              {{ resumen.tramos_salario_adicionales }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Días de vacaciones a migrar (saldo)
            </dt>
            <dd class="font-medium text-gray-900 dark:text-white">
              {{ resumen.dias_vacaciones_acumulados_totales }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              ISR del año a cargar
            </dt>
            <dd class="font-medium text-gray-900 dark:text-white">
              ${{ resumen.isr_total_a_cargar }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">
              Meses de bruto histórico cargados
            </dt>
            <dd class="font-medium text-gray-900 dark:text-white">
              {{ resumen.meses_bruto_historico_cargados }}
            </dd>
          </div>
        </dl>
        <div class="flex gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :disabled="cargandoConfirmar"
            @click="volverAEditar"
          >
            Volver
          </UButton>
          <UButton
            :loading="cargandoConfirmar"
            @click="onConfirmar"
          >
            Confirmar migración
          </UButton>
        </div>
      </UCard>

      <UCard v-if="paso === 'confirmado' && resumenFinal">
        <div class="flex items-center gap-2 mb-3 text-green-600 dark:text-green-400">
          <UIcon
            name="i-lucide-check-circle"
            class="size-5"
          />
          <p class="font-medium">
            Migración confirmada
          </p>
        </div>
        <p class="text-sm text-gray-500 mb-4">
          Se cargaron {{ resumenFinal.empleados }} empleado(s). Ya podés generar planillas con normalidad.
        </p>
        <UButton to="/empleados">
          Ir a Empleados
        </UButton>
      </UCard>
    </template>
  </div>
</template>

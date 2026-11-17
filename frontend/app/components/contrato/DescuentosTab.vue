<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Contrato } from '~/composables/useContratos'
import type { CuotaDescuento, Descuento, SimulacionDescuento, TipoDescuento } from '~/composables/useDescuentos'
import { ETIQUETAS_TIPO_DESCUENTO } from '~/composables/useDescuentos'

const props = defineProps<{ contrato: Contrato }>()

const { listar, simular, registrar, listarCuotas, cerrar, eliminar, obtenerDocumentoUrl, subirDocumento } = useDescuentos()
const { puedeEscribir } = useAuth()
const toast = useToast()

const { data: descuentos, refresh } = await useAsyncData(
  `descuentos-${props.contrato.id}`, () => listar(props.contrato.id)
)

const urlsDocumento = reactive<Record<string, string>>({})
async function cargarDocumentos() {
  for (const d of descuentos.value ?? []) {
    if (d.tiene_documento && !urlsDocumento[d.id]) {
      const url = await obtenerDocumentoUrl(d.id)
      if (url) urlsDocumento[d.id] = url
    }
  }
}
await cargarDocumentos()

// Préstamos con monto y plazo obligatorios; los demás pueden ser una
// cuota fija sin fecha de fin (pensión, cooperativa, embargo).
const TIPOS_CON_PLAZO: TipoDescuento[] = ['prestamo_empresa', 'prestamo_bancario', 'hipoteca']

const opcionesTipo = Object.entries(ETIQUETAS_TIPO_DESCUENTO).map(([value, label]) => ({ label, value }))
const opcionesFrecuencia = [
  { label: 'Quincenal (2 pagos al mes)', value: 'quincenal' },
  { label: 'Mensual (1 pago al mes)', value: 'mensual' }
]

const mostrarFormulario = ref(false)
const schema = z.object({
  tipo: z.enum(['prestamo_empresa', 'prestamo_bancario', 'hipoteca', 'cooperativa', 'pension_alimenticia', 'embargo']),
  acreedor: z.string().min(1, 'Obligatorio'),
  referencia: z.string().optional(),
  cuota_fija: z.boolean(),
  monto_total: z.number().positive('Debe ser mayor que cero').optional(),
  plazo_meses: z.number().int().min(1, 'Mínimo 1 mes').optional(),
  cuota: z.number().positive('Debe ser mayor que cero').optional(),
  frecuencia: z.enum(['quincenal', 'mensual']),
  fecha_inicio: z.string().min(1, 'Obligatorio'),
  observacion: z.string().optional()
}).superRefine((datos, ctx) => {
  if (datos.cuota_fija) {
    if (!datos.cuota) ctx.addIssue({ code: 'custom', path: ['cuota'], message: 'Obligatorio' })
  } else {
    if (!datos.monto_total) ctx.addIssue({ code: 'custom', path: ['monto_total'], message: 'Obligatorio' })
    if (!datos.plazo_meses) ctx.addIssue({ code: 'custom', path: ['plazo_meses'], message: 'Obligatorio' })
  }
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({
  tipo: 'prestamo_bancario',
  acreedor: '',
  referencia: '',
  cuota_fija: false,
  monto_total: undefined,
  plazo_meses: undefined,
  cuota: undefined,
  frecuencia: 'quincenal',
  fecha_inicio: '',
  observacion: ''
})
const guardando = ref(false)
const archivoDocumento = ref<HTMLInputElement>()
const nombreArchivoElegido = ref('')

const permiteCuotaFija = computed(() => !TIPOS_CON_PLAZO.includes(state.tipo as TipoDescuento))
watch(() => state.tipo, (tipo) => {
  if (tipo && TIPOS_CON_PLAZO.includes(tipo)) state.cuota_fija = false
  else if (tipo === 'pension_alimenticia' || tipo === 'cooperativa') state.cuota_fija = true
  if (tipo === 'prestamo_empresa' && !state.acreedor) state.acreedor = 'Empresa'
})

const ayudaMonto = computed(() => state.tipo === 'prestamo_empresa'
  ? 'Solo el capital prestado: un préstamo de la empresa no puede cobrar intereses (Art. 165 CT).'
  : 'El total a pagar que indica la carta de descuento (capital más intereses).')

// La cuota la calcula el backend (nunca el frontend): se pide una
// simulación cada vez que cambian monto, plazo, frecuencia o fecha.
const simulacion = ref<SimulacionDescuento | null>(null)
let temporizadorSimulacion: ReturnType<typeof setTimeout> | undefined
watch(
  () => [state.cuota_fija, state.monto_total, state.plazo_meses, state.frecuencia, state.fecha_inicio],
  () => {
    clearTimeout(temporizadorSimulacion)
    simulacion.value = null
    if (state.cuota_fija || !state.monto_total || !state.plazo_meses || !state.fecha_inicio) return
    temporizadorSimulacion = setTimeout(async () => {
      try {
        simulacion.value = await simular(props.contrato.id, {
          monto_total: state.monto_total,
          plazo_meses: state.plazo_meses,
          frecuencia: state.frecuencia,
          fecha_inicio: state.fecha_inicio
        })
      } catch {
        simulacion.value = null
      }
    }, 300)
  }
)

function onArchivoElegido() {
  nombreArchivoElegido.value = archivoDocumento.value?.files?.[0]?.name ?? ''
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const datos = event.data
    const body: Record<string, unknown> = {
      tipo: datos.tipo,
      acreedor: datos.acreedor,
      frecuencia: datos.frecuencia,
      fecha_inicio: datos.fecha_inicio
    }
    if (datos.referencia) body.referencia = datos.referencia
    if (datos.observacion) body.observacion = datos.observacion
    if (datos.cuota_fija) {
      body.cuota = datos.cuota
    } else {
      body.monto_total = datos.monto_total
      body.plazo_meses = datos.plazo_meses
    }
    const descuento = await registrar(props.contrato.id, body)
    const archivo = archivoDocumento.value?.files?.[0]
    if (archivo) await subirDocumento(descuento.id, archivo)
    toast.add({ title: 'Descuento registrado', color: 'success' })
    mostrarFormulario.value = false
    Object.assign(state, { acreedor: '', referencia: '', monto_total: undefined, plazo_meses: undefined, cuota: undefined, observacion: '' })
    if (archivoDocumento.value) archivoDocumento.value.value = ''
    nombreArchivoElegido.value = ''
    await refresh()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

const COLOR_ESTADO: Record<Descuento['estado_actual'], 'success' | 'neutral' | 'warning' | 'info'> = {
  activo: 'success',
  pagado: 'info',
  cerrado: 'neutral',
  terminado: 'warning'
}
const ETIQUETA_ESTADO: Record<Descuento['estado_actual'], string> = {
  activo: 'Activo',
  pagado: 'Pagado',
  cerrado: 'Cerrado',
  terminado: 'Contrato terminado'
}
const ETIQUETA_ORIGEN: Record<CuotaDescuento['origen'], string> = {
  quincenal: 'Planilla quincenal',
  mensual: 'Planilla mensual',
  vacaciones: 'Pago de vacaciones',
  liquidacion: 'Liquidación'
}

const expandido = ref<string | null>(null)
const cuotas = reactive<Record<string, CuotaDescuento[]>>({})
async function alternarCuotas(descuentoId: string) {
  if (expandido.value === descuentoId) {
    expandido.value = null
    return
  }
  expandido.value = descuentoId
  try {
    cuotas[descuentoId] = await listarCuotas(descuentoId)
  } catch (error) {
    toast.add({ title: 'No se pudieron cargar las cuotas', description: extraerMensajeError(error), color: 'error' })
  }
}

const cerrandoId = ref<string | null>(null)
const motivoCierre = ref('')
const guardandoCierre = ref(false)
async function confirmarCierre(descuentoId: string) {
  if (!motivoCierre.value.trim()) {
    toast.add({ title: 'Escribe el motivo del cierre', color: 'warning' })
    return
  }
  guardandoCierre.value = true
  try {
    await cerrar(descuentoId, motivoCierre.value.trim())
    toast.add({ title: 'Descuento cerrado', color: 'success' })
    cerrandoId.value = null
    motivoCierre.value = ''
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo cerrar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardandoCierre.value = false
  }
}

const eliminandoId = ref<string | null>(null)
async function borrar(descuentoId: string) {
  try {
    await eliminar(descuentoId)
    toast.add({ title: 'Descuento eliminado', color: 'success' })
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo eliminar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    eliminandoId.value = null
  }
}

const subiendoDocumentoDe = ref<string | null>(null)
const inputsDocumentoExistente = reactive<Record<string, HTMLInputElement | undefined>>({})
async function subirDocumentoExistente(descuentoId: string) {
  const archivo = inputsDocumentoExistente[descuentoId]?.files?.[0]
  if (!archivo) return
  subiendoDocumentoDe.value = descuentoId
  try {
    await subirDocumento(descuentoId, archivo)
    toast.add({ title: 'Documento subido', color: 'success' })
    await refresh()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo subir el documento', description: extraerMensajeError(error), color: 'error' })
  } finally {
    subiendoDocumentoDe.value = null
    const input = inputsDocumentoExistente[descuentoId]
    if (input) input.value = ''
  }
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="puedeEscribir && contrato.estado === 'vigente'"
      class="flex justify-end"
    >
      <UButton
        size="sm"
        icon="i-lucide-plus"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Registrar préstamo o descuento
      </UButton>
    </div>

    <UCard v-if="mostrarFormulario && puedeEscribir">
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo"
          name="tipo"
        >
          <USelect
            v-model="state.tipo"
            :items="opcionesTipo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Acreedor"
          name="acreedor"
          help="Banco, financiera, cooperativa o juzgado al que se le paga."
        >
          <UInput
            v-model="state.acreedor"
            class="w-full"
            placeholder="Ej. Banco General"
          />
        </UFormField>
        <UFormField
          label="Referencia"
          name="referencia"
          help="N.º de préstamo, de carta o de expediente."
        >
          <UInput
            v-model="state.referencia"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Frecuencia de pago"
          name="frecuencia"
        >
          <USelect
            v-model="state.frecuencia"
            :items="opcionesFrecuencia"
            value-key="value"
            class="w-full"
          />
        </UFormField>

        <UFormField
          v-if="permiteCuotaFija"
          name="cuota_fija"
          class="col-span-2"
        >
          <UCheckbox
            v-model="state.cuota_fija"
            label="Cuota fija sin fecha de fin (se cobra hasta que se cierre)"
          />
        </UFormField>

        <template v-if="!state.cuota_fija">
          <UFormField
            label="Monto del préstamo"
            name="monto_total"
            :help="ayudaMonto"
          >
            <UInputNumber
              v-model="state.monto_total"
              :min="0.01"
              :step="0.01"
              class="w-full"
            />
          </UFormField>
          <UFormField
            label="Plazo (meses)"
            name="plazo_meses"
          >
            <UInputNumber
              v-model="state.plazo_meses"
              :min="1"
              :step="1"
              class="w-full"
            />
          </UFormField>
        </template>
        <UFormField
          v-else
          label="Cuota por pago"
          name="cuota"
        >
          <UInputNumber
            v-model="state.cuota"
            :min="0.01"
            :step="0.01"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Cobrar desde"
          name="fecha_inicio"
          help="Se cobra el 15 y el último día de cada mes (quincenal) o el último día del mes (mensual)."
        >
          <UInput
            v-model="state.fecha_inicio"
            type="date"
            class="w-full"
          />
        </UFormField>

        <div
          v-if="simulacion"
          class="col-span-2 rounded-md bg-gray-50 dark:bg-gray-800/50 p-3 text-sm"
        >
          <span class="font-medium text-gray-900 dark:text-white">
            {{ simulacion.numero_cuotas }} cuotas de ${{ simulacion.cuota }}
          </span>
          <span
            v-if="simulacion.ultima_cuota !== simulacion.cuota"
            class="text-gray-500"
          >
            (la última de ${{ simulacion.ultima_cuota }})
          </span>
          <span class="text-gray-500">
            — del {{ formatearFecha(simulacion.fecha_primera_cuota) }} al {{ formatearFecha(simulacion.fecha_ultima_cuota) }}
          </span>
        </div>

        <UFormField
          label="Observación"
          name="observacion"
          class="col-span-2"
        >
          <UInput
            v-model="state.observacion"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Carta de descuento u orden (opcional)"
          name="documento"
          class="col-span-2"
          help="El documento se sube automáticamente al presionar Guardar."
        >
          <input
            ref="archivoDocumento"
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            class="hidden"
            @change="onArchivoElegido"
          >
          <div class="flex items-center gap-3">
            <UButton
              type="button"
              icon="i-lucide-paperclip"
              color="neutral"
              variant="outline"
              @click="archivoDocumento?.click()"
            >
              Seleccionar archivo
            </UButton>
            <span class="text-sm text-gray-500">
              {{ nombreArchivoElegido || 'Ningún archivo seleccionado' }}
            </span>
          </div>
        </UFormField>
        <div class="flex gap-2 col-span-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Guardar
          </UButton>
          <UButton
            color="neutral"
            variant="ghost"
            @click="mostrarFormulario = false"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>

    <UCard>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
              <th class="py-2 pr-4">
                Tipo / acreedor
              </th>
              <th class="py-2 pr-4">
                Monto
              </th>
              <th class="py-2 pr-4">
                Cuota
              </th>
              <th class="py-2 pr-4">
                Cobradas
              </th>
              <th class="py-2 pr-4">
                Saldo
              </th>
              <th class="py-2 pr-4">
                Estado
              </th>
              <th class="py-2 pr-4">
                Documento
              </th>
              <th class="py-2" />
            </tr>
          </thead>
          <tbody>
            <template
              v-for="d in descuentos"
              :key="d.id"
            >
              <tr class="border-b border-gray-100 dark:border-gray-800">
                <td class="py-2 pr-4">
                  <div class="font-medium text-gray-900 dark:text-white">
                    {{ d.acreedor }}
                  </div>
                  <div class="text-xs text-gray-500">
                    {{ ETIQUETAS_TIPO_DESCUENTO[d.tipo] }}<span v-if="d.referencia"> · ref. {{ d.referencia }}</span>
                  </div>
                </td>
                <td class="py-2 pr-4">
                  <span v-if="d.monto_total">${{ d.monto_total }}<span class="text-xs text-gray-500"> / {{ d.plazo_meses }} meses</span></span>
                  <span
                    v-else
                    class="text-gray-500"
                  >Sin fecha de fin</span>
                </td>
                <td class="py-2 pr-4">
                  ${{ d.cuota }} <span class="text-xs text-gray-500">{{ d.frecuencia }}</span>
                </td>
                <td class="py-2 pr-4">
                  {{ d.cuotas_cobradas }}<span v-if="d.numero_cuotas"> de {{ d.numero_cuotas }}</span>
                  <div class="text-xs text-gray-500">
                    ${{ d.total_cobrado }}
                  </div>
                </td>
                <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
                  {{ d.saldo === null ? '—' : `$${d.saldo}` }}
                </td>
                <td class="py-2 pr-4">
                  <UBadge
                    :color="COLOR_ESTADO[d.estado_actual]"
                    variant="subtle"
                  >
                    {{ ETIQUETA_ESTADO[d.estado_actual] }}
                  </UBadge>
                </td>
                <td class="py-2 pr-4 text-gray-500">
                  <a
                    v-if="urlsDocumento[d.id]"
                    :href="urlsDocumento[d.id]"
                    target="_blank"
                    class="text-primary-500 hover:underline"
                  >
                    {{ d.documento_nombre_archivo || 'Ver documento' }}
                  </a>
                  <div v-else-if="puedeEscribir">
                    <input
                      :ref="(el) => { inputsDocumentoExistente[d.id] = el as HTMLInputElement | undefined }"
                      type="file"
                      accept="application/pdf,image/png,image/jpeg"
                      class="hidden"
                      @change="subirDocumentoExistente(d.id)"
                    >
                    <UButton
                      size="xs"
                      icon="i-lucide-upload"
                      color="neutral"
                      variant="outline"
                      :loading="subiendoDocumentoDe === d.id"
                      @click="inputsDocumentoExistente[d.id]?.click()"
                    >
                      Subir
                    </UButton>
                  </div>
                  <span v-else>—</span>
                </td>
                <td class="py-2 text-right whitespace-nowrap">
                  <UButton
                    size="xs"
                    variant="ghost"
                    color="neutral"
                    :icon="expandido === d.id ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                    @click="alternarCuotas(d.id)"
                  >
                    Cuotas
                  </UButton>
                  <template v-if="puedeEscribir && d.estado_actual === 'activo'">
                    <UButton
                      size="xs"
                      variant="ghost"
                      color="neutral"
                      icon="i-lucide-circle-stop"
                      @click="cerrandoId = cerrandoId === d.id ? null : d.id"
                    >
                      Cerrar
                    </UButton>
                    <template v-if="d.cuotas_cobradas === 0">
                      <template v-if="eliminandoId === d.id">
                        <UButton
                          size="xs"
                          color="error"
                          @click="borrar(d.id)"
                        >
                          Sí, eliminar
                        </UButton>
                        <UButton
                          size="xs"
                          variant="ghost"
                          color="neutral"
                          @click="eliminandoId = null"
                        >
                          No
                        </UButton>
                      </template>
                      <UButton
                        v-else
                        size="xs"
                        color="error"
                        variant="ghost"
                        icon="i-lucide-trash-2"
                        @click="eliminandoId = d.id"
                      />
                    </template>
                  </template>
                </td>
              </tr>
              <tr v-if="cerrandoId === d.id">
                <td
                  colspan="8"
                  class="py-3 bg-gray-50 dark:bg-gray-800/50"
                >
                  <div class="flex items-center gap-2 px-2">
                    <UInput
                      v-model="motivoCierre"
                      class="flex-1"
                      placeholder="Motivo del cierre (ej. carta de cancelación del banco)"
                    />
                    <UButton
                      size="sm"
                      :loading="guardandoCierre"
                      @click="confirmarCierre(d.id)"
                    >
                      Cerrar descuento
                    </UButton>
                    <UButton
                      size="sm"
                      variant="ghost"
                      color="neutral"
                      @click="cerrandoId = null"
                    >
                      Cancelar
                    </UButton>
                  </div>
                </td>
              </tr>
              <tr v-if="expandido === d.id">
                <td
                  colspan="8"
                  class="py-3 bg-gray-50 dark:bg-gray-800/50"
                >
                  <div class="px-2 space-y-1">
                    <p
                      v-if="d.motivo_cierre"
                      class="text-xs text-gray-500"
                    >
                      Cerrado el {{ formatearFecha(d.fecha_cierre ?? '') }}: {{ d.motivo_cierre }}
                    </p>
                    <p
                      v-if="d.observacion"
                      class="text-xs text-gray-500"
                    >
                      {{ d.observacion }}
                    </p>
                    <table
                      v-if="cuotas[d.id]?.length"
                      class="w-full text-xs"
                    >
                      <tbody>
                        <tr
                          v-for="c in cuotas[d.id]"
                          :key="c.id"
                          :class="c.anulada ? 'line-through text-gray-400' : ''"
                        >
                          <td class="py-1 pr-4">
                            {{ formatearFecha(c.fecha_cobro) }}
                          </td>
                          <td class="py-1 pr-4">
                            {{ ETIQUETA_ORIGEN[c.origen] }}<span v-if="c.anulada"> (anulada)</span>
                          </td>
                          <td class="py-1 pr-4 text-right">
                            ${{ c.monto }}
                            <span
                              v-if="c.monto !== c.monto_programado"
                              class="text-warning"
                            >de ${{ c.monto_programado }}</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <p
                      v-else
                      class="text-xs text-gray-500"
                    >
                      Todavía no se ha cobrado ninguna cuota.
                    </p>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!descuentos || descuentos.length === 0">
              <td
                colspan="8"
                class="py-8 text-center text-gray-500"
              >
                Sin préstamos ni descuentos registrados.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </div>
</template>

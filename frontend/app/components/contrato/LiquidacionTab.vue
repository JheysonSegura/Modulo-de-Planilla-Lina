<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Contrato } from '~/composables/useContratos'

const props = defineProps<{ contrato: Contrato }>()
const emit = defineEmits<{ 'contrato-actualizado': [] }>()

const { listarDeContrato, generar, aprobar, anular, pagar, obtenerConstanciaPagoUrl } = useLiquidaciones()
const { descargar } = useReportes()
const { puedeEscribir } = useAuth()
const toast = useToast()

const { data: liquidaciones, refresh } = await useAsyncData(
  `liquidaciones-${props.contrato.id}`, () => listarDeContrato(props.contrato.id)
)

const constanciaUrls = reactive<Record<string, string>>({})
async function cargarConstancias() {
  for (const liq of liquidaciones.value ?? []) {
    if (liq.tiene_constancia_pago && !constanciaUrls[liq.id]) {
      const url = await obtenerConstanciaPagoUrl(liq.id)
      if (url) constanciaUrls[liq.id] = url
    }
  }
}
await cargarConstancias()

const mostrarFormulario = ref(false)
const schema = z.object({
  motivo: z.enum([
    'renuncia_voluntaria', 'renuncia_justificada', 'despido_justificado',
    'despido_causa_economica', 'despido_injustificado', 'mutuo_acuerdo'
  ]),
  fecha_terminacion: z.string().min(1, 'Obligatorio'),
  otras_deducciones: z.number().min(0).optional(),
  monto_salarios_caidos: z.number().min(0).optional(),
  referencia_sentencia: z.string().optional(),
  fecha_aviso_renuncia: z.string().optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({
  motivo: 'renuncia_voluntaria',
  fecha_terminacion: '',
  otras_deducciones: 0,
  monto_salarios_caidos: 0,
  referencia_sentencia: '',
  fecha_aviso_renuncia: ''
})
const guardando = ref(false)

const opcionesMotivo = [
  { label: 'Renuncia voluntaria', value: 'renuncia_voluntaria' },
  { label: 'Renuncia justificada', value: 'renuncia_justificada' },
  { label: 'Despido justificado', value: 'despido_justificado' },
  { label: 'Despido por causa económica', value: 'despido_causa_economica' },
  { label: 'Despido injustificado', value: 'despido_injustificado' },
  { label: 'Mutuo acuerdo', value: 'mutuo_acuerdo' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.referencia_sentencia) delete body.referencia_sentencia
    if (!body.fecha_aviso_renuncia) delete body.fecha_aviso_renuncia
    await generar(props.contrato.id, body)
    toast.add({ title: 'Liquidación generada', color: 'success' })
    mostrarFormulario.value = false
    await refresh()
    emit('contrato-actualizado')
  } catch (error) {
    toast.add({ title: 'No se pudo generar la liquidación', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

const descargando = ref(false)
async function descargarRecibo(liquidacionId: string, motivo: string, formato: 'pdf' | 'excel') {
  descargando.value = true
  const extension = formato === 'pdf' ? 'pdf' : 'xlsx'
  try {
    await descargar(
      `/liquidaciones/${liquidacionId}/recibo`,
      { formato },
      `recibo-liquidacion-${motivo}.${extension}`
    )
  } catch (error) {
    toast.add({ title: 'No se pudo descargar el recibo', description: extraerMensajeError(error), color: 'error' })
  } finally {
    descargando.value = false
  }
}

const aprobandoId = ref<string | null>(null)
async function aprobarLiquidacion(liquidacionId: string) {
  aprobandoId.value = liquidacionId
  try {
    await aprobar(liquidacionId)
    toast.add({ title: 'Liquidación aprobada', color: 'success' })
    await refresh()
  } catch (error) {
    toast.add({ title: 'No se pudo aprobar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    aprobandoId.value = null
  }
}

const anulandoId = ref<string | null>(null)
const confirmandoAnularId = ref<string | null>(null)
async function anularLiquidacion(liquidacionId: string) {
  anulandoId.value = liquidacionId
  try {
    await anular(liquidacionId)
    toast.add({ title: 'Liquidación anulada', color: 'success' })
    await refresh()
    emit('contrato-actualizado')
  } catch (error) {
    toast.add({ title: 'No se pudo anular', description: extraerMensajeError(error), color: 'error' })
  } finally {
    anulandoId.value = null
    confirmandoAnularId.value = null
  }
}

const pagando = ref(false)
const modalPagoAbierto = ref(false)
const liquidacionParaPagar = ref<string | null>(null)

function abrirModalPago(liquidacionId: string) {
  liquidacionParaPagar.value = liquidacionId
  modalPagoAbierto.value = true
}

async function onConfirmarPago({ archivo }: { archivo: File, motivo?: string }) {
  if (!liquidacionParaPagar.value) return
  pagando.value = true
  try {
    await pagar(liquidacionParaPagar.value, archivo)
    toast.add({ title: 'Pago confirmado', color: 'success' })
    await refresh()
    await cargarConstancias()
    modalPagoAbierto.value = false
  } catch (error) {
    toast.add({ title: 'No se pudo confirmar el pago', description: extraerMensajeError(error), color: 'error' })
  } finally {
    pagando.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <UButton
      v-if="contrato.estado === 'vigente' && !mostrarFormulario && puedeEscribir"
      size="sm"
      color="error"
      variant="soft"
      icon="i-lucide-file-minus"
      @click="mostrarFormulario = true"
    >
      Generar liquidación
    </UButton>

    <UCard v-if="mostrarFormulario && puedeEscribir">
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Motivo"
          name="motivo"
          class="col-span-2"
        >
          <USelect
            v-model="state.motivo"
            :items="opcionesMotivo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Fecha de terminación"
          name="fecha_terminacion"
        >
          <UInput
            v-model="state.fecha_terminacion"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          v-if="state.motivo === 'renuncia_voluntaria'"
          label="Fecha de aviso de renuncia"
          name="fecha_aviso_renuncia"
        >
          <UInput
            v-model="state.fecha_aviso_renuncia"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Otras deducciones"
          name="otras_deducciones"
        >
          <UInputNumber
            v-model="state.otras_deducciones"
            :min="0"
            :step="0.01"
            class="w-full"
          />
        </UFormField>
        <UFormField
          v-if="['despido_injustificado', 'despido_causa_economica'].includes(state.motivo ?? '')"
          label="Salarios caídos (sentencia judicial)"
          name="monto_salarios_caidos"
        >
          <UInputNumber
            v-model="state.monto_salarios_caidos"
            :min="0"
            :step="0.01"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Referencia de sentencia"
          name="referencia_sentencia"
          class="col-span-2"
        >
          <UInput
            v-model="state.referencia_sentencia"
            class="w-full"
          />
        </UFormField>
        <div class="col-span-2 flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Generar
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

    <UCard
      v-for="liq in liquidaciones"
      :key="liq.id"
    >
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">Liquidación — {{ liq.motivo }}</span>
          <div class="flex items-center gap-2">
            <UBadge variant="subtle">
              {{ liq.estado }}
            </UBadge>
            <UButton
              size="xs"
              variant="ghost"
              color="neutral"
              icon="i-lucide-file-text"
              :loading="descargando"
              @click="descargarRecibo(liq.id, liq.motivo, 'pdf')"
            >
              PDF
            </UButton>
            <UButton
              size="xs"
              variant="ghost"
              color="neutral"
              icon="i-lucide-file-spreadsheet"
              :loading="descargando"
              @click="descargarRecibo(liq.id, liq.motivo, 'excel')"
            >
              Excel
            </UButton>

            <template v-if="liq.estado === 'borrador' && puedeEscribir">
              <template v-if="confirmandoAnularId === liq.id">
                <span class="text-sm text-gray-500">¿Seguro?</span>
                <UButton
                  size="xs"
                  color="error"
                  :loading="anulandoId === liq.id"
                  @click="anularLiquidacion(liq.id)"
                >
                  Sí, anular
                </UButton>
                <UButton
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :disabled="anulandoId === liq.id"
                  @click="confirmandoAnularId = null"
                >
                  Cancelar
                </UButton>
              </template>
              <template v-else>
                <UButton
                  size="xs"
                  variant="soft"
                  color="error"
                  icon="i-lucide-ban"
                  @click="confirmandoAnularId = liq.id"
                >
                  Anular
                </UButton>
                <UButton
                  size="xs"
                  :loading="aprobandoId === liq.id"
                  icon="i-lucide-check"
                  @click="aprobarLiquidacion(liq.id)"
                >
                  Aprobar
                </UButton>
              </template>
            </template>

            <UButton
              v-if="liq.estado === 'aprobada' && puedeEscribir"
              size="xs"
              icon="i-lucide-banknote"
              @click="abrirModalPago(liq.id)"
            >
              Confirmar pago
            </UButton>

            <a
              v-if="liq.estado === 'pagada' && constanciaUrls[liq.id]"
              :href="constanciaUrls[liq.id]"
              target="_blank"
              class="text-sm text-primary-500 hover:underline flex items-center gap-1"
            >
              <UIcon name="i-lucide-file-check" /> Ver constancia de pago
            </a>
          </div>
        </div>
      </template>
      <dl class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <dt class="text-gray-500">
            Salario pendiente
          </dt><dd>${{ liq.salario_pendiente }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Décimo proporcional
          </dt><dd>${{ liq.decimo_proporcional }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Vacaciones pendientes
          </dt><dd>${{ liq.vacaciones_pendientes }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Prima de antigüedad
          </dt><dd>${{ liq.prima_antiguedad }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Indemnización
          </dt><dd>${{ liq.indemnizacion }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Preaviso
          </dt><dd>${{ liq.preaviso }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Salarios caídos
          </dt><dd>${{ liq.salarios_caidos }}</dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Penalidad renuncia sin aviso
          </dt><dd class="text-error">
            -${{ liq.penalidad_renuncia_sin_aviso }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Otras deducciones
          </dt><dd class="text-error">
            -${{ liq.otras_deducciones }}
          </dd>
        </div>
      </dl>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-800 text-right">
        <span class="text-gray-500 mr-2">Total:</span>
        <span class="text-xl font-semibold text-gray-900 dark:text-white">${{ liq.monto_total }}</span>
      </div>
    </UCard>

    <p
      v-if="!liquidaciones || liquidaciones.length === 0"
      class="text-center text-gray-500 py-8"
    >
      Este contrato no tiene liquidaciones.
    </p>

    <ConstanciaPagoModal
      v-model:open="modalPagoAbierto"
      modo="confirmar"
      entidad="liquidacion"
      :cargando="pagando"
      @confirmar="onConfirmarPago"
    />
  </div>
</template>

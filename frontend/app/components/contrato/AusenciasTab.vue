<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const props = defineProps<{ contratoId: string }>()

const { listar, registrar, obtenerDocumentoUrl, subirDocumento } = useAusencias()
const toast = useToast()

const { data: ausencias, refresh } = await useAsyncData(`ausencias-${props.contratoId}`, () => listar(props.contratoId))

const urlsDocumento = reactive<Record<string, string>>({})

async function cargarDocumentos() {
  for (const ausencia of ausencias.value ?? []) {
    if (ausencia.tiene_documento_constancia && !urlsDocumento[ausencia.id]) {
      const url = await obtenerDocumentoUrl(ausencia.id)
      if (url) urlsDocumento[ausencia.id] = url
    }
  }
}
await cargarDocumentos()

const mostrarFormulario = ref(false)
const nombreArchivoElegido = ref('')
const subiendoDocumentoDe = ref<string | null>(null)
const inputsDocumentoExistente = reactive<Record<string, HTMLInputElement | undefined>>({})
const schema = z.object({
  tipo: z.enum([
    'enfermedad_dentro_fondo', 'enfermedad_excede_fondo', 'embarazo', 'riesgo_profesional',
    'huelga_legal', 'licencia_sindical_o_estado', 'licencia_autorizada_empleador',
    'arresto_o_prision_preventiva', 'injustificada'
  ]),
  fecha_desde: z.string().min(1, 'Obligatorio'),
  fecha_hasta: z.string().min(1, 'Obligatorio'),
  certificado_ref: z.string().optional()
})
type Schema = z.output<typeof schema>
const state = reactive<Partial<Schema>>({ tipo: 'injustificada', fecha_desde: '', fecha_hasta: '', certificado_ref: '' })
const guardando = ref(false)
const archivoConstancia = ref<HTMLInputElement>()

const opcionesTipo = [
  { label: 'Enfermedad (dentro del fondo)', value: 'enfermedad_dentro_fondo' },
  { label: 'Enfermedad (excede el fondo)', value: 'enfermedad_excede_fondo' },
  { label: 'Embarazo', value: 'embarazo' },
  { label: 'Riesgo profesional', value: 'riesgo_profesional' },
  { label: 'Huelga legal', value: 'huelga_legal' },
  { label: 'Licencia sindical o del Estado', value: 'licencia_sindical_o_estado' },
  { label: 'Licencia autorizada por el empleador', value: 'licencia_autorizada_empleador' },
  { label: 'Arresto o prisión preventiva', value: 'arresto_o_prision_preventiva' },
  { label: 'Injustificada', value: 'injustificada' }
]

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body: Record<string, unknown> = { ...event.data }
    if (!body.certificado_ref) delete body.certificado_ref
    const ausencia = await registrar(props.contratoId, body)

    const archivo = archivoConstancia.value?.files?.[0]
    if (archivo) {
      await subirDocumento(ausencia.id, archivo)
    }

    toast.add({ title: 'Ausencia registrada', color: 'success' })
    mostrarFormulario.value = false
    if (archivoConstancia.value) archivoConstancia.value.value = ''
    nombreArchivoElegido.value = ''
    await refresh()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo registrar', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}

function onArchivoElegido() {
  nombreArchivoElegido.value = archivoConstancia.value?.files?.[0]?.name ?? ''
}

async function subirDocumentoExistente(ausenciaId: string) {
  const archivo = inputsDocumentoExistente[ausenciaId]?.files?.[0]
  if (!archivo) return
  subiendoDocumentoDe.value = ausenciaId
  try {
    await subirDocumento(ausenciaId, archivo)
    toast.add({ title: 'Documento subido', color: 'success' })
    await refresh()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo subir el documento', description: extraerMensajeError(error), color: 'error' })
  } finally {
    subiendoDocumentoDe.value = null
    const input = inputsDocumentoExistente[ausenciaId]
    if (input) input.value = ''
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-end">
      <UButton
        size="sm"
        icon="i-lucide-plus"
        @click="mostrarFormulario = !mostrarFormulario"
      >
        Registrar ausencia
      </UButton>
    </div>

    <UCard v-if="mostrarFormulario">
      <UForm
        :schema="schema"
        :state="state"
        class="grid grid-cols-2 gap-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo"
          name="tipo"
          class="col-span-2"
        >
          <USelect
            v-model="state.tipo"
            :items="opcionesTipo"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Desde"
          name="fecha_desde"
        >
          <UInput
            v-model="state.fecha_desde"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Hasta"
          name="fecha_hasta"
        >
          <UInput
            v-model="state.fecha_hasta"
            type="date"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Referencia de certificado"
          name="certificado_ref"
          class="col-span-2"
        >
          <UInput
            v-model="state.certificado_ref"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Documento de constancia (opcional)"
          name="documento_constancia"
          class="col-span-2"
          help="El documento se sube automáticamente al presionar Guardar."
        >
          <input
            ref="archivoConstancia"
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
              @click="archivoConstancia?.click()"
            >
              Seleccionar archivo
            </UButton>
            <span class="text-sm text-gray-500">
              {{ nombreArchivoElegido || 'Ningún archivo seleccionado' }}
            </span>
          </div>
        </UFormField>
        <UButton
          type="submit"
          class="w-fit"
          :loading="guardando"
        >
          Guardar
        </UButton>
      </UForm>
    </UCard>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Tipo
            </th>
            <th class="py-2 pr-4">
              Desde
            </th>
            <th class="py-2 pr-4">
              Hasta
            </th>
            <th class="py-2 pr-4">
              Certificado
            </th>
            <th class="py-2">
              Documento
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="a in ausencias"
            :key="a.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4">
              {{ a.tipo }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(a.fecha_desde) }}
            </td>
            <td class="py-2 pr-4">
              {{ formatearFecha(a.fecha_hasta) }}
            </td>
            <td class="py-2 pr-4 text-gray-500">
              {{ a.certificado_ref || '—' }}
            </td>
            <td class="py-2 text-gray-500">
              <a
                v-if="urlsDocumento[a.id]"
                :href="urlsDocumento[a.id]"
                target="_blank"
                class="text-primary-500 hover:underline"
              >
                {{ a.documento_constancia_nombre_archivo || 'Ver documento' }}
              </a>
              <div
                v-else
                class="flex items-center gap-2"
              >
                <input
                  :ref="(el) => { inputsDocumentoExistente[a.id] = el as HTMLInputElement | undefined }"
                  type="file"
                  accept="application/pdf,image/png,image/jpeg"
                  class="hidden"
                  @change="subirDocumentoExistente(a.id)"
                >
                <UButton
                  size="xs"
                  icon="i-lucide-upload"
                  color="neutral"
                  variant="outline"
                  :loading="subiendoDocumentoDe === a.id"
                  @click="inputsDocumentoExistente[a.id]?.click()"
                >
                  Subir documento
                </UButton>
              </div>
            </td>
          </tr>
          <tr v-if="!ausencias || ausencias.length === 0">
            <td
              colspan="5"
              class="py-8 text-center text-gray-500"
            >
              Sin ausencias registradas.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

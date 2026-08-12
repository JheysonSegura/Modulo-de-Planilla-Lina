<script setup lang="ts">
const props = defineProps<{
  open: boolean
  modo: 'confirmar' | 'reemplazar'
  cargando: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirmar': [payload: { archivo: File, motivo?: string }]
}>()

const inputArchivo = ref<HTMLInputElement>()
const archivo = ref<File | null>(null)
const motivo = ref('')

watch(() => props.open, (abierto) => {
  if (!abierto) {
    archivo.value = null
    motivo.value = ''
    if (inputArchivo.value) inputArchivo.value.value = ''
  }
})

function onSeleccionarArchivo(event: Event) {
  archivo.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

const puedeConfirmar = computed(() =>
  !!archivo.value && (props.modo === 'confirmar' || motivo.value.trim().length > 0)
)

function confirmar() {
  if (!archivo.value || !puedeConfirmar.value) return
  emit('confirmar', props.modo === 'reemplazar'
    ? { archivo: archivo.value, motivo: motivo.value.trim() }
    : { archivo: archivo.value })
}

function cancelar() {
  emit('update:open', false)
}

const titulo = computed(() =>
  props.modo === 'confirmar' ? 'Confirmar pago de planilla' : 'Reemplazar constancia de pago'
)
const textoBoton = computed(() =>
  props.modo === 'confirmar' ? 'Confirmar pago' : 'Reemplazar constancia'
)
</script>

<template>
  <UModal
    :open="open"
    :title="titulo"
    :dismissible="!cargando"
    :close="!cargando"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #body>
      <p
        v-if="modo === 'confirmar'"
        class="text-sm text-gray-500 mb-3"
      >
        Esta acción marca la planilla como pagada y no se puede deshacer. Verificá que el archivo
        sea la constancia bancaria correcta antes de confirmar.
      </p>
      <p
        v-else
        class="text-sm text-gray-500 mb-3"
      >
        Vas a reemplazar la constancia de una planilla ya pagada. La planilla se queda en estado
        "pagada"; solo cambia el archivo adjunto. Esta acción queda registrada en auditoría.
      </p>

      <UButton
        variant="soft"
        color="neutral"
        icon="i-lucide-paperclip"
        @click="inputArchivo?.click()"
      >
        {{ archivo ? archivo.name : 'Seleccionar archivo' }}
      </UButton>
      <input
        ref="inputArchivo"
        type="file"
        accept="application/pdf,image/png,image/jpeg"
        class="hidden"
        @change="onSeleccionarArchivo"
      >

      <UTextarea
        v-if="modo === 'reemplazar'"
        v-model="motivo"
        placeholder="Motivo del reemplazo (obligatorio) — ej. se subió el comprobante equivocado"
        class="w-full mt-3"
        :rows="3"
      />
    </template>

    <template #footer>
      <UButton
        variant="ghost"
        color="neutral"
        :disabled="cargando"
        @click="cancelar"
      >
        Cancelar
      </UButton>
      <UButton
        :loading="cargando"
        :disabled="!puedeConfirmar"
        @click="confirmar"
      >
        {{ textoBoton }}
      </UButton>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const { listar } = useAuditoria()

const filtroTabla = ref<string | undefined>(undefined)
const filtroAccion = ref<string | undefined>(undefined)

const { data: eventos, pending, refresh } = await useAsyncData(
  'auditoria', () => listar(undefined, filtroTabla.value, filtroAccion.value),
  { watch: [filtroTabla, filtroAccion] }
)

const opcionesTabla = [
  { label: 'Todas', value: undefined },
  { label: 'Contratos (salario)', value: 'contratos' },
  { label: 'Planillas', value: 'planillas' },
  { label: 'Liquidaciones', value: 'liquidaciones' },
  { label: 'Usuarios de la empresa', value: 'usuarios_empresas' }
]
const opcionesAccion = [
  { label: 'Todas', value: undefined },
  { label: 'Cambio de salario', value: 'cambio_salario' },
  { label: 'Planilla aprobada', value: 'aprobada' },
  { label: 'Liquidación calculada', value: 'calculada' },
  { label: 'Liquidación pagada', value: 'pagada' },
  { label: 'Acceso otorgado', value: 'acceso_otorgado' },
  { label: 'Rol cambiado', value: 'rol_cambiado' },
  { label: 'Acceso revocado', value: 'acceso_revocado' }
]

function formatearFecha(fecha: string) {
  return new Date(fecha).toLocaleString('es-PA')
}

onActivated(() => refresh())
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      Auditoría
    </h1>

    <div class="flex gap-3 mb-4">
      <USelect
        v-model="filtroTabla"
        :items="opcionesTabla"
        value-key="value"
        placeholder="Tabla afectada"
        class="w-56"
      />
      <USelect
        v-model="filtroAccion"
        :items="opcionesAccion"
        value-key="value"
        placeholder="Tipo de evento"
        class="w-56"
      />
    </div>

    <UCard>
      <div
        v-if="pending"
        class="text-center py-8 text-gray-500"
      >
        Cargando...
      </div>
      <div
        v-else
        class="space-y-2"
      >
        <div
          v-for="evento in eventos"
          :key="evento.id"
          class="border border-gray-200 dark:border-gray-800 rounded-md p-3"
        >
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <UBadge variant="subtle">
                {{ evento.tabla_afectada }}
              </UBadge>
              <span class="text-sm font-medium text-gray-900 dark:text-white">{{ evento.accion }}</span>
            </div>
            <span class="text-xs text-gray-500">{{ formatearFecha(evento.created_at) }}</span>
          </div>
          <div class="grid grid-cols-2 gap-4 text-xs mt-2">
            <div v-if="evento.datos_anteriores">
              <div class="text-gray-500 mb-1">
                Antes
              </div>
              <pre class="bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-x-auto">{{ evento.datos_anteriores }}</pre>
            </div>
            <div v-if="evento.datos_nuevos">
              <div class="text-gray-500 mb-1">
                Después
              </div>
              <pre class="bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-x-auto">{{ evento.datos_nuevos }}</pre>
            </div>
          </div>
        </div>
        <p
          v-if="!eventos || eventos.length === 0"
          class="text-center text-gray-500 py-8"
        >
          Sin eventos registrados.
        </p>
      </div>
    </UCard>
  </div>
</template>

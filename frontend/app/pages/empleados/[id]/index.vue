<script setup lang="ts">
const route = useRoute()
const empleadoId = route.params.id as string

const {
  obtener,
  obtenerDocumentoIdentificacionUrl,
  subirDocumentoIdentificacion,
  obtenerDocumentoCertificadoMedicoUrl,
  subirDocumentoCertificadoMedico
} = useEmpleados()
const { listarDeEmpleado } = useContratos()
const toast = useToast()

const { data: empleado, refresh: refrescarEmpleado } = await useAsyncData(`empleado-${empleadoId}`, () => obtener(empleadoId))
const { data: contratos, refresh: refrescarContratos } = await useAsyncData(
  `contratos-${empleadoId}`, () => listarDeEmpleado(empleadoId)
)

onActivated(() => refrescarContratos())

const sexoLabel: Record<string, string> = { masculino: 'Masculino', femenino: 'Femenino', otro: 'Otro' }

const urlDocumentoIdentificacion = ref<string | null>(null)
const urlDocumentoCertificadoMedico = ref<string | null>(null)
const subiendoIdentificacion = ref(false)
const subiendoCertificadoMedico = ref(false)
const inputIdentificacion = ref<HTMLInputElement>()
const inputCertificadoMedico = ref<HTMLInputElement>()

async function cargarDocumentos() {
  urlDocumentoIdentificacion.value = empleado.value?.tiene_documento_identificacion
    ? await obtenerDocumentoIdentificacionUrl(empleadoId)
    : null
  urlDocumentoCertificadoMedico.value = empleado.value?.tiene_documento_certificado_medico
    ? await obtenerDocumentoCertificadoMedicoUrl(empleadoId)
    : null
}
await cargarDocumentos()

async function onSeleccionarIdentificacion(event: Event) {
  const archivo = (event.target as HTMLInputElement).files?.[0]
  if (!archivo) return
  subiendoIdentificacion.value = true
  try {
    await subirDocumentoIdentificacion(empleadoId, archivo)
    toast.add({ title: 'Documento de identificación actualizado', color: 'success' })
    await refrescarEmpleado()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo subir el documento', description: String(error), color: 'error' })
  } finally {
    subiendoIdentificacion.value = false
    if (inputIdentificacion.value) inputIdentificacion.value.value = ''
  }
}

async function onSeleccionarCertificadoMedico(event: Event) {
  const archivo = (event.target as HTMLInputElement).files?.[0]
  if (!archivo) return
  subiendoCertificadoMedico.value = true
  try {
    await subirDocumentoCertificadoMedico(empleadoId, archivo)
    toast.add({ title: 'Certificado médico actualizado', color: 'success' })
    await refrescarEmpleado()
    await cargarDocumentos()
  } catch (error) {
    toast.add({ title: 'No se pudo subir el documento', description: String(error), color: 'error' })
  } finally {
    subiendoCertificadoMedico.value = false
    if (inputCertificadoMedico.value) inputCertificadoMedico.value.value = ''
  }
}
</script>

<template>
  <div v-if="empleado">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ empleado.nombre_completo }}
        </h1>
        <p class="text-sm text-gray-500">
          {{ empleado.identificacion }} · {{ empleado.tipo_identificacion }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <UBadge
          :color="empleado.estado === 'activo' ? 'success' : 'neutral'"
          variant="subtle"
        >
          {{ empleado.estado }}
        </UBadge>
        <UButton
          size="sm"
          color="neutral"
          variant="subtle"
          icon="i-lucide-pencil"
          :to="`/empleados/${empleadoId}/editar`"
        >
          Editar
        </UButton>
      </div>
    </div>

    <UCard class="mb-6">
      <template #header>
        <span class="font-medium">Datos personales</span>
      </template>
      <dl class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <dt class="text-gray-500">
            Email personal
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.email_personal || '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Teléfono
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.telefono ? `${empleado.codigo_pais ?? ''} ${empleado.telefono}`.trim() : '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Dirección
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.direccion || '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Fecha de nacimiento
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.fecha_nacimiento ? formatearFecha(empleado.fecha_nacimiento) : '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Sexo
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.sexo ? sexoLabel[empleado.sexo] : '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-gray-500">
            Nacionalidad
          </dt>
          <dd class="text-gray-900 dark:text-white">
            {{ empleado.nacionalidad || '—' }}
          </dd>
        </div>
        <div class="col-span-2 sm:col-span-3">
          <dt class="text-gray-500">
            Enfermedad
          </dt>
          <dd class="text-gray-900 dark:text-white">
            <template v-if="empleado.padece_enfermedad">
              Sí<span v-if="empleado.detalle_enfermedad"> — {{ empleado.detalle_enfermedad }}</span>
            </template>
            <template v-else>
              No
            </template>
          </dd>
        </div>
      </dl>
    </UCard>

    <UCard class="mb-6">
      <template #header>
        <span class="font-medium">Documentos</span>
      </template>
      <div class="space-y-4 text-sm">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-900 dark:text-white font-medium">
              Cédula / identificación
            </p>
            <a
              v-if="urlDocumentoIdentificacion"
              :href="urlDocumentoIdentificacion"
              target="_blank"
              class="text-primary-500 hover:underline"
            >
              {{ empleado.documento_identificacion_nombre_archivo || 'Ver documento' }}
            </a>
            <p
              v-else
              class="text-gray-500"
            >
              Sin documento cargado.
            </p>
          </div>
          <div>
            <input
              ref="inputIdentificacion"
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              class="hidden"
              @change="onSeleccionarIdentificacion"
            >
            <UButton
              size="sm"
              color="neutral"
              variant="subtle"
              :loading="subiendoIdentificacion"
              @click="inputIdentificacion?.click()"
            >
              {{ urlDocumentoIdentificacion ? 'Cambiar' : 'Subir' }}
            </UButton>
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-900 dark:text-white font-medium">
              Certificado médico
            </p>
            <a
              v-if="urlDocumentoCertificadoMedico"
              :href="urlDocumentoCertificadoMedico"
              target="_blank"
              class="text-primary-500 hover:underline"
            >
              {{ empleado.documento_certificado_medico_nombre_archivo || 'Ver documento' }}
            </a>
            <p
              v-else
              class="text-gray-500"
            >
              Sin documento cargado.
            </p>
          </div>
          <div>
            <input
              ref="inputCertificadoMedico"
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              class="hidden"
              @change="onSeleccionarCertificadoMedico"
            >
            <UButton
              size="sm"
              color="neutral"
              variant="subtle"
              :loading="subiendoCertificadoMedico"
              @click="inputCertificadoMedico?.click()"
            >
              {{ urlDocumentoCertificadoMedico ? 'Cambiar' : 'Subir' }}
            </UButton>
          </div>
        </div>
      </div>
    </UCard>

    <div class="flex items-center justify-between mb-3">
      <h2 class="font-medium text-gray-900 dark:text-white">
        Contratos
      </h2>
      <UButton
        size="sm"
        icon="i-lucide-plus"
        :to="`/empleados/${empleadoId}/contratos/nuevo`"
      >
        Nuevo contrato
      </UButton>
    </div>

    <UCard>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-200 dark:border-gray-800">
            <th class="py-2 pr-4">
              Cargo
            </th>
            <th class="py-2 pr-4">
              Tipo
            </th>
            <th class="py-2 pr-4">
              Inicio
            </th>
            <th class="py-2 pr-4">
              Estado
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="contrato in contratos"
            :key="contrato.id"
            class="border-b border-gray-100 dark:border-gray-800 last:border-0"
          >
            <td class="py-2 pr-4 font-medium text-gray-900 dark:text-white">
              {{ contrato.cargo }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ contrato.tipo_contrato }}
            </td>
            <td class="py-2 pr-4 text-gray-600 dark:text-gray-400">
              {{ formatearFecha(contrato.fecha_inicio) }}
            </td>
            <td class="py-2 pr-4">
              <UBadge
                :color="contrato.estado === 'vigente' ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ contrato.estado }}
              </UBadge>
            </td>
            <td class="py-2 text-right">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-chevron-right"
                :to="`/empleados/${empleadoId}/contratos/${contrato.id}`"
              />
            </td>
          </tr>
          <tr v-if="!contratos || contratos.length === 0">
            <td
              colspan="5"
              class="py-8 text-center text-gray-500"
            >
              Sin contratos todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </UCard>
  </div>
</template>

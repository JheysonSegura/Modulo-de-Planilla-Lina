<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const route = useRoute()
const empleadoId = route.params.id as string

const { obtener, actualizar } = useEmpleados()
const toast = useToast()

const { data: empleado } = await useAsyncData(`empleado-editar-${empleadoId}`, () => obtener(empleadoId))

const schema = z.object({
  fecha_nacimiento: z.string().optional()
    .refine(v => !v || esMayorDeEdad(v), 'El empleado debe ser mayor de edad (18 años o más).'),
  sexo: z.enum(['masculino', 'femenino', 'otro']).optional(),
  nacionalidad: z.string().optional(),
  codigo_pais: z.string().optional(),
  telefono: z.string().optional(),
  direccion: z.string().optional(),
  padece_enfermedad: z.boolean().optional(),
  detalle_enfermedad: z.string().optional()
})
type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({
  fecha_nacimiento: empleado.value?.fecha_nacimiento ?? undefined,
  sexo: empleado.value?.sexo ?? undefined,
  nacionalidad: empleado.value?.nacionalidad ?? undefined,
  codigo_pais: empleado.value?.codigo_pais ?? undefined,
  telefono: empleado.value?.telefono ?? undefined,
  direccion: empleado.value?.direccion ?? undefined,
  padece_enfermedad: empleado.value?.padece_enfermedad ?? false,
  detalle_enfermedad: empleado.value?.detalle_enfermedad ?? undefined
})

const guardando = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    await actualizar(empleadoId, event.data)
    toast.add({ title: 'Empleado actualizado', color: 'success' })
    await navigateTo(`/empleados/${empleadoId}`)
  } catch (error) {
    toast.add({ title: 'No se pudo actualizar el empleado', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div
    v-if="empleado"
    class="max-w-xl"
  >
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-1">
      Editar empleado
    </h1>
    <p class="text-sm text-gray-500 mb-4">
      {{ empleado.nombre_completo }} · {{ empleado.identificacion }}
    </p>
    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <EmpleadoFormDatosPersonales :state="state" />

        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Guardar cambios
          </UButton>
          <UButton
            :to="`/empleados/${empleadoId}`"
            color="neutral"
            variant="ghost"
          >
            Cancelar
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

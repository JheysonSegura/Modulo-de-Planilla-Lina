<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'

const { crear } = useEmpleados()
const toast = useToast()

const schema = z.object({
  tipo_identificacion: z.enum(['cedula', 'pasaporte']),
  identificacion: z.string().min(1, 'Obligatorio'),
  nombre_completo: z.string().min(1, 'Obligatorio'),
  fecha_nacimiento: z.string().optional()
    .refine(v => !v || esMayorDeEdad(v), 'El empleado debe ser mayor de edad (18 años o más).'),
  sexo: z.enum(['masculino', 'femenino', 'otro']).optional(),
  nacionalidad: z.string().optional(),
  email_personal: z.string().email('Email inválido').optional().or(z.literal('')),
  codigo_pais: z.string().optional(),
  telefono: z.string().optional(),
  direccion: z.string().optional(),
  padece_enfermedad: z.boolean().optional(),
  detalle_enfermedad: z.string().optional()
})
type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({
  tipo_identificacion: 'cedula',
  identificacion: '',
  nombre_completo: '',
  email_personal: '',
  telefono: '',
  direccion: '',
  padece_enfermedad: false
})

const opcionesTipoId = [
  { label: 'Cédula', value: 'cedula' },
  { label: 'Pasaporte', value: 'pasaporte' }
]

const guardando = ref(false)

async function onSubmit(event: FormSubmitEvent<Schema>) {
  guardando.value = true
  try {
    const body = { ...event.data }
    if (!body.email_personal) delete body.email_personal
    const empleado = await crear(body)
    toast.add({ title: 'Empleado creado', color: 'success' })
    await navigateTo(`/empleados/${empleado.id}`)
  } catch (error) {
    toast.add({ title: 'No se pudo crear el empleado', description: extraerMensajeError(error), color: 'error' })
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <div class="max-w-xl">
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      Nuevo empleado
    </h1>
    <UCard>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField
          label="Tipo de identificación"
          name="tipo_identificacion"
        >
          <USelect
            v-model="state.tipo_identificacion"
            :items="opcionesTipoId"
            value-key="value"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Identificación"
          name="identificacion"
        >
          <UInput
            v-model="state.identificacion"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Nombre completo"
          name="nombre_completo"
        >
          <UInput
            v-model="state.nombre_completo"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Email personal"
          name="email_personal"
        >
          <UInput
            v-model="state.email_personal"
            type="email"
            class="w-full"
          />
        </UFormField>

        <EmpleadoFormDatosPersonales :state="state" />

        <div class="flex gap-2">
          <UButton
            type="submit"
            :loading="guardando"
          >
            Crear empleado
          </UButton>
          <UButton
            to="/empleados"
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

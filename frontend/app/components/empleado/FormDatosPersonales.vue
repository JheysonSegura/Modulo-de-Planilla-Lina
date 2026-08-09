<script setup lang="ts">
import { opcionesPaisesTelefono } from '~/utils/paisesTelefono'
import type { DatosPersonalesForm } from '~/composables/useEmpleados'

const props = defineProps<{ state: DatosPersonalesForm }>()
const state = props.state

const opcionesSexo = [
  { label: 'Masculino', value: 'masculino' },
  { label: 'Femenino', value: 'femenino' },
  { label: 'Otro', value: 'otro' }
]
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <UFormField
        label="Fecha de nacimiento"
        name="fecha_nacimiento"
      >
        <UInput
          v-model="state.fecha_nacimiento"
          type="date"
          :max="fechaMaximaMayorDeEdad()"
          class="w-full"
        />
      </UFormField>
      <UFormField
        label="Sexo"
        name="sexo"
      >
        <USelect
          v-model="state.sexo"
          :items="opcionesSexo"
          value-key="value"
          class="w-full"
        />
      </UFormField>
    </div>

    <UFormField
      label="Nacionalidad"
      name="nacionalidad"
    >
      <UInput
        v-model="state.nacionalidad"
        class="w-full"
      />
    </UFormField>

    <UFormField
      label="Teléfono"
      name="telefono"
    >
      <div class="flex gap-2">
        <USelect
          v-model="state.codigo_pais"
          :items="opcionesPaisesTelefono"
          value-key="value"
          class="w-40 shrink-0"
        />
        <UInput
          v-model="state.telefono"
          class="w-full"
        />
      </div>
    </UFormField>

    <UFormField
      label="Dirección"
      name="direccion"
    >
      <UTextarea
        v-model="state.direccion"
        class="w-full"
      />
    </UFormField>

    <UFormField name="padece_enfermedad">
      <UCheckbox
        v-model="state.padece_enfermedad"
        label="Padece de una enfermedad"
      />
    </UFormField>

    <UFormField
      v-if="state.padece_enfermedad"
      label="Detalle de la enfermedad"
      name="detalle_enfermedad"
    >
      <UTextarea
        v-model="state.detalle_enfermedad"
        placeholder="Opcional"
        class="w-full"
      />
    </UFormField>
  </div>
</template>

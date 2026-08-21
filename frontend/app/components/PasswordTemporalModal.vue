<script setup lang="ts">
defineProps<{
  open: boolean
  passwordTemporal: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()
</script>

<template>
  <UModal
    :open="open"
    title="Contraseña temporal generada"
    :dismissible="false"
    :close="false"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #body>
      <p class="text-sm text-gray-500 mb-3">
        Copiala ahora — no se va a volver a mostrar. Es de un solo uso: el usuario deberá definir
        su propia contraseña permanente en su próximo inicio de sesión. Vence en 24 horas si nadie
        la usa.
      </p>
      <UInput
        :model-value="passwordTemporal"
        readonly
        class="w-full font-mono"
      />
    </template>
    <template #footer>
      <UButton @click="emit('update:open', false)">
        Cerrar
      </UButton>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const { accessToken, logout } = useAuth()

async function salir() {
  await logout()
  await navigateTo('/login')
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-950 px-4">
    <div class="absolute top-4 right-4 flex items-center gap-2">
      <UColorModeButton />
      <UButton
        v-if="accessToken"
        icon="i-lucide-log-out"
        color="neutral"
        variant="ghost"
        @click="salir"
      >
        Salir
      </UButton>
    </div>
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">
          Nómina Panamá
        </h1>
      </div>
      <slot />
    </div>
  </div>
</template>

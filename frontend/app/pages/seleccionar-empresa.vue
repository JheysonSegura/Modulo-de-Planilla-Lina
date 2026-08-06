<script setup lang="ts">
import type { EmpresaAcceso } from '~/composables/useAuth'

definePageMeta({ layout: 'publico' })

const { listarEmpresas, seleccionarEmpresa, accessToken } = useAuth()

if (!accessToken.value) {
  await navigateTo('/login')
}

const { data: empresas, pending, error } = await useAsyncData<EmpresaAcceso[]>(
  'auth-empresas',
  () => listarEmpresas()
)

const seleccionando = ref<string | null>(null)

async function elegir(empresaId: string) {
  seleccionando.value = empresaId
  try {
    await seleccionarEmpresa(empresaId)
    await navigateTo('/')
  } finally {
    seleccionando.value = null
  }
}
</script>

<template>
  <div class="space-y-4">
    <p class="text-center text-gray-600 dark:text-gray-400">
      Elige la empresa con la que quieres trabajar
    </p>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      title="No se pudieron cargar tus empresas."
    />
    <div
      v-else-if="pending"
      class="text-center text-gray-500"
    >
      Cargando...
    </div>

    <UCard
      v-for="empresa in empresas"
      :key="empresa.empresa_id"
      class="cursor-pointer hover:ring-2 hover:ring-primary transition"
      @click="elegir(empresa.empresa_id)"
    >
      <div class="flex items-center justify-between">
        <div>
          <div class="font-medium text-gray-900 dark:text-white">
            {{ empresa.nombre_comercial || empresa.razon_social }}
          </div>
          <div class="text-sm text-gray-500">
            {{ empresa.razon_social }}
          </div>
        </div>
        <div class="flex items-center gap-3">
          <UBadge
            color="secondary"
            variant="subtle"
          >
            {{ empresa.rol }}
          </UBadge>
          <UIcon
            v-if="seleccionando === empresa.empresa_id"
            name="i-lucide-loader-2"
            class="animate-spin"
          />
          <UIcon
            v-else
            name="i-lucide-chevron-right"
          />
        </div>
      </div>
    </UCard>

    <p
      v-if="empresas && empresas.length === 0"
      class="text-center text-gray-500"
    >
      No tienes acceso a ninguna empresa todavía. Contacta a tu administrador.
    </p>
  </div>
</template>

<script setup lang="ts">
const { usuario, empresaActiva, rolActivo, logout } = useAuth()
const route = useRoute()

const navegacion = computed(() => {
  const items = [
    { to: '/', label: 'Inicio', icon: 'i-lucide-home' },
    { to: '/empleados', label: 'Empleados', icon: 'i-lucide-users' },
    { to: '/planillas', label: 'Planillas', icon: 'i-lucide-banknote' },
    { to: '/parametros-legales', label: 'Parámetros legales', icon: 'i-lucide-scale' },
    { to: '/empresa', label: 'Empresa', icon: 'i-lucide-building-2' }
  ]
  if (rolActivo.value === 'admin') {
    items.push(
      { to: '/empresa/usuarios', label: 'Usuarios', icon: 'i-lucide-shield-user' },
      { to: '/auditoria', label: 'Auditoría', icon: 'i-lucide-history' }
    )
  }
  return items
})

function esRutaActiva(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}

async function salir() {
  await logout()
  await navigateTo('/login')
}
</script>

<template>
  <div class="min-h-screen flex bg-gray-100 dark:bg-gray-950">
    <aside class="w-64 shrink-0 flex flex-col bg-[var(--color-navy-900)] text-gray-100">
      <div class="h-16 flex items-center px-5 text-lg font-semibold text-white border-b border-white/10">
        Nómina Panamá
      </div>
      <nav class="flex-1 py-4 space-y-1 px-3">
        <NuxtLink
          v-for="item in navegacion"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors"
          :class="esRutaActiva(item.to)
            ? 'bg-[var(--color-navy-800)] text-white'
            : 'text-gray-300 hover:bg-[var(--color-navy-800)] hover:text-white'"
        >
          <UIcon
            :name="item.icon"
            class="size-5"
          />
          {{ item.label }}
        </NuxtLink>
      </nav>
    </aside>

    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-16 shrink-0 flex items-center justify-between px-6 bg-white dark:bg-gray-900 border-b border-gray-300 dark:border-gray-800">
        <div class="text-sm text-gray-600 dark:text-gray-400">
          <span class="font-medium text-gray-900 dark:text-white">
            {{ empresaActiva?.nombre_comercial || empresaActiva?.razon_social }}
          </span>
        </div>
        <div class="flex items-center gap-4">
          <UColorModeButton />
          <div class="text-right text-sm">
            <div class="text-gray-900 dark:text-white font-medium">
              {{ usuario?.nombre_completo }}
            </div>
            <UBadge
              color="secondary"
              variant="subtle"
              size="sm"
            >
              {{ rolActivo }}
            </UBadge>
          </div>
          <UButton
            icon="i-lucide-log-out"
            color="neutral"
            variant="ghost"
            @click="salir"
          >
            Salir
          </UButton>
        </div>
      </header>

      <main class="flex-1 p-6 overflow-y-auto">
        <slot />
      </main>
    </div>
  </div>
</template>

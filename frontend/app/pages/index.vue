<script setup lang="ts">
const { usuario, rolActivo } = useAuth()

const accesos = computed(() => {
  const items = [
    { to: '/empleados', label: 'Empleados', desc: 'Fichas, contratos e historial salarial', icon: 'i-lucide-users' },
    { to: '/planillas', label: 'Planillas', desc: 'Generar y revisar planillas', icon: 'i-lucide-banknote' },
    { to: '/parametros-legales', label: 'Parámetros legales', desc: 'CSS, ISR, salario mínimo, riesgo profesional', icon: 'i-lucide-scale' }
  ]
  if (rolActivo.value === 'admin') {
    items.push({ to: '/auditoria', label: 'Auditoría', desc: 'Trazabilidad de cambios sensibles', icon: 'i-lucide-history' })
  }
  return items
})
</script>

<template>
  <div>
    <h1 class="text-xl font-semibold text-gray-900 dark:text-white mb-1">
      Hola, {{ usuario?.nombre_completo }}
    </h1>
    <p class="text-gray-500 mb-6">
      ¿Qué necesitas hacer hoy?
    </p>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink
        v-for="item in accesos"
        :key="item.to"
        :to="item.to"
      >
        <UCard class="h-full hover:ring-2 hover:ring-primary transition">
          <div class="flex items-start gap-3">
            <UIcon
              :name="item.icon"
              class="size-6 text-primary shrink-0"
            />
            <div>
              <div class="font-medium text-gray-900 dark:text-white">{{ item.label }}</div>
              <div class="text-sm text-gray-500">{{ item.desc }}</div>
            </div>
          </div>
        </UCard>
      </NuxtLink>
    </div>
  </div>
</template>

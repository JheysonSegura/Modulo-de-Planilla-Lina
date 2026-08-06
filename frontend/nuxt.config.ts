// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui'
  ],

  // App interna detrás de login (no hay contenido público que se
  // beneficie de SSR/SEO) -- SPA pura evita toda la complejidad de
  // sincronizar el estado de sesión (JWT, empresa activa) entre
  // servidor y cliente en cada request.
  ssr: false,

  devtools: {
    enabled: true
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // Mapeado desde NUXT_PUBLIC_API_BASE (docker-compose.yml / .env).
      // Sin esta clave declarada, Nuxt no expone esa variable de
      // entorno al cliente aunque el contenedor la reciba.
      apiBase: 'http://localhost:8000'
    }
  },

  compatibilityDate: '2026-06-30',

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})

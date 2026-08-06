export default defineNuxtPlugin(async () => {
  const { hidratarSesion } = useAuth()
  // Se espera antes de montar la app (ssr:false + plugin async) para
  // que el middleware de auth ya vea usuario/empresa/rol poblados en
  // la primera navegación, no solo en las siguientes.
  await hidratarSesion()
})

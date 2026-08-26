# Auditoría de Seguridad — Nómina Panamá
**Fecha:** 2026-08-25 · **Alcance:** código completo (backend FastAPI, frontend Nuxt/Vue, Docker, historial de git) · **Commit auditado:** `d5fd74f` (origin/master, repo limpio)

## Estado de remediación (actualizado 2026-08-25, misma sesión)

Los 6 hallazgos Críticos y Altos que admitían un fix acotado quedaron **arreglados y verificados** (suite completa 211/211 backend + lint/typecheck frontend en verde, más pruebas manuales puntuales por hallazgo). Repo sin commitear todavía -- pendiente de decisión del usuario.

| # | Hallazgo | Estado |
|---|---|---|
| C1 | Secretos default inseguros en `config.py` | ✅ Arreglado — la app ahora rechaza arrancar en producción con los secretos de desarrollo (verificado con `ENVIRONMENT=production` real) |
| C2 | Sin rate limiting en login/reset | ✅ Arreglado — `slowapi`, 5/min en login y cambiar-password-temporal, 20/min en refresh (verificado: 6º intento da 429) |
| A1 | Dependencias con CVEs | ✅ Arreglado — `python-multipart`, `starlette`/`fastapi`, `PyJWT`, `weasyprint`/`pydyf`, `jinja2`, `python-dotenv` actualizados; frontend `nanoid` vía `npm audit fix`. `esbuild` (Baja, solo dev server) queda aceptado sin fix -- forzarlo exige bump mayor de Nuxt/Vite, desproporcionado para un riesgo bajo y no productivo |
| A3 | Sin headers de seguridad HTTP | ✅ Arreglado — middleware con CSP-adjacent headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `HSTS`) |
| A4 | Contenedores root / sin compose de producción / Postgres expuesto | ✅ Arreglado — `Dockerfile.prod` (backend y frontend, no-root, sin bind-mount) + `docker-compose.prod.yml` (Postgres sin publicar, healthchecks, `restart: unless-stopped`) + `.env.production.example`. Probado con un stack de producción real levantado en paralelo (puertos distintos). **Nota:** NO se tocó el `Dockerfile` de desarrollo -- se intentó usuario no-root ahí también pero rompió el bind-mount (esta carpeta está sincronizada con OneDrive y el mapeo de permisos Unix sobre ese bind-mount en Windows no es confiable); revertido sin diff |
| A5 | Sin límite de tamaño en uploads | ✅ Arreglado — helper `core/uploads.py`, aplicado en los 6 endpoints de subida (logo 5MB, documentos 10MB, Excel migración 20MB) |
| A2 | Tokens JWT en cookies sin `httpOnly` | ⏸ **Diferido a pedido explícito del usuario** — requiere rediseño completo del mecanismo de sesión (backend `deps.py`/`auth_service.py`/CORS + frontend `useAuth.ts`/`useApi.ts` completos), alto riesgo de regresión. Mitigado en buena parte por A3 (CSP reduce la probabilidad de XSS, que es el vector real de robo de token en el diseño actual). Recomendación: abordarlo en una sesión dedicada con testing exhaustivo en navegador real. |

## Estado de remediación — Medios y Bajos (actualizado 2026-08-26)

| # | Hallazgo | Estado |
|---|---|---|
| M1 | Recibo de pago: falta validar la planilla padre antes del movimiento | ✅ Arreglado — `recibo_pago` llama `obtener_planilla` antes de `obtener_movimiento`, igual que `recibos_pago_zip` |
| M2 | `movimientos_planilla`/`historial_salarial` sin RLS propio | ✅ Arreglado — migración `0036_rls_movimientos_historial`: `empresa_id` denormalizado + backfill + `ENABLE/FORCE ROW LEVEL SECURITY` + política de aislamiento, mismo patrón que `provisiones_decimo`/`provisiones_vacaciones`. Los 6 sitios que crean estos registros (`contratos_service`, `planilla_service`, `decimo_service`, `migracion_service`) ahora pasan `empresa_id` explícito |
| M3 | `/docs`/`/redoc`/`/openapi.json` expuestos sin restricción | ✅ Arreglado — deshabilitados cuando `ENVIRONMENT=production` |
| M4 | Validación de archivos solo por `Content-Type` declarado | ✅ Arreglado — `core/uploads.py::validar_firma_imagen`/`validar_firma_excel` verifican magic bytes reales (PNG/JPEG/WEBP) y escanean SVG por `<script>`/`on*=`/`javascript:`; aplicado en logo de empresa y Excel de migración |
| M5 | Sin logging de eventos de seguridad | ✅ Arreglado — logger `nomina.seguridad`: intentos de login fallidos (email+IP, nunca password) en `auth_service.autenticar`, resets de contraseña en `usuarios_service.resetear_password` (los 3 endpoints) |
| M6 | Sin estrategia de backups de BD | ✅ Arreglado — servicio `backup` en `docker-compose.prod.yml` (imagen propia en `scripts/backup/`): `pg_dump` periódico comprimido a un volumen `db_backups` que backend/frontend NUNCA montan (aislado de la app), con purga por retención (`BACKUP_RETENCION_DIAS`, default 14 días) y `scripts/backup/restaurar.sh` para probar la restauración periódicamente contra una BD descartable. Verificado end-to-end con un stack de producción real levantado en paralelo: se generaron backups reales, se corrieron las migraciones, y se restauró un dump con esquema + datos semilla en una base nueva sin errores |
| B1 | Password mínimo de 8 sin complejidad | ✅ Arreglado — mínimo subido a 10 (backend + validación espejo en frontend) |
| B2 | CORS con `allow_methods`/`allow_headers` wildcard | ✅ Arreglado — acotado a los métodos/headers que el frontend realmente usa |
| B3 | Cookies del frontend sin `secure` explícito | ✅ Arreglado — `secure: !import.meta.dev` en `useAuth.ts` |
| B4 | Campos de texto libre sin `max_length` | ✅ Arreglado — `direccion`, `detalle_enfermedad`, `certificado_ref` ahora tienen tope |
| B5 | Imágenes Docker sin digest | Sin tocar — fuera de alcance de esta sesión |
| B6 | HTTPS/HSTS depende de infraestructura externa | ✅ Reverse proxy dejado armado — servicio `proxy` (Caddy) en `docker-compose.prod.yml`, con HTTPS automático (Let's Encrypt) para `DOMINIO_FRONTEND`/`DOMINIO_API` y `Strict-Transport-Security` explícito en el frontend (el backend ya lo manda desde A3). `backend`/`frontend` dejaron de publicar sus puertos a `0.0.0.0` — el proxy es la única puerta de entrada pública; ahora solo quedan en loopback para debug vía túnel SSH. Verificado el enrutamiento end-to-end (health check + un POST real a `/auth/login`) contra un stack aislado con dominios de prueba en HTTP plano — la emisión de un certificado real todavía no es verificable porque **no existe dominio/servidor elegido**, así que esa parte queda pendiente de activar el día que se elijan (ver comentarios en `docker-compose.prod.yml` y `scripts/proxy/Caddyfile`) |

Pendiente explícito: A2 (JWT en cookies httpOnly, diferido); B5 (sin tocar, no urgente); y la emisión real del certificado TLS de B6, que depende de que exista un dominio/servidor real (el reverse proxy que lo hará ya está armado).

---

## Resumen ejecutivo

**Nivel de riesgo actual: ALTO para exposición inmediata a internet — pero la arquitectura de fondo es sólida.**

Lo bueno primero, porque importa para decidir cuánto esfuerzo hace falta: el diseño de autenticación (bcrypt, JWT con algoritmo fijo, rotación real de refresh tokens, protección contra enumeración de usuarios, contraseñas temporales con CSPRNG) y el de autorización multi-tenant (RLS forzado en Postgres con un rol de aplicación no-superusuario, roles admin/contador/consulta aplicados de forma consistente en prácticamente todos los endpoints de escritura) están **bien implementados**. No se encontró SQL injection, command injection, SSRF, XXE, ni XSS explotable. `.env` nunca se filtró en el historial de git.

Lo que hace que el riesgo sea alto hoy es un conjunto de **gaps de hardening perimetral y de configuración**, todos con fix barato y bien entendido:

1. Valores por defecto inseguros para `JWT_SECRET_KEY` y credenciales de Postgres que se activan solos si algo falla al desplegar (secreto público en este mismo repo).
2. Cero rate limiting en login/reset de contraseña — fuerza bruta sin fricción contra cualquier cuenta.
3. Dependencias con CVEs reales y explotables hoy (`python-multipart`, usado en 2 endpoints de subida de archivos expuestos).
4. Sin ningún header de seguridad HTTP, sin límite de tamaño de archivos subidos, contenedores corriendo como root, Postgres publicado a todas las interfaces, y **no existe ningún `docker-compose` de producción** (el único que hay corre en modo desarrollo: `--reload`, `npm run dev`, código montado como volumen).

Ninguno de estos 4 puntos requiere rediseñar nada — son cambios acotados. Con ellos resueltos, el riesgo baja a moderado/bajo.

---

## Hallazgos — CRÍTICA

### C1. Secretos por defecto inseguros en `config.py` (JWT + credenciales de Postgres)
**Archivo:** `backend/app/core/config.py:11-24`
```python
database_url: str = "postgresql+psycopg://nomina_app:nomina_app_dev@db:5432/nomina"
database_url_admin: str = "postgresql+psycopg://nomina:nomina@db:5432/nomina"
postgres_app_password: str = "nomina_app_dev"
jwt_secret_key: str = "dev-secret-change-me"
```
`Settings` es un `BaseSettings` de Pydantic: si la variable de entorno correspondiente no está seteada (typo, `.env` incompleto en el servidor nuevo, contenedor levantado a mano para debug), estos defaults se usan **silenciosamente**, sin error ni warning. Los 4 valores son públicos (están en este repo).

**Escenario de explotación:** si en el deploy de producción falta `JWT_SECRET_KEY`, la app arranca igual con `"dev-secret-change-me"`. Cualquiera puede forjar un JWT HS256 válido (`{"rol": "admin", "empresa_id": "<cualquiera>", ...}`) firmado con ese string público → acceso admin total a cualquier empresa, bypass completo de RLS y autenticación. Igual de grave si se reutilizan las credenciales de Postgres por descuido y la BD queda alcanzable en red (ver A3).

**Fix recomendado:**
```python
# Sin default para el secreto real:
jwt_secret_key: str  # Pydantic falla al arrancar si falta la env var

# O, si se prefiere no romper dev, validar explícitamente:
@model_validator(mode="after")
def _validar_produccion(self):
    if self.environment != "development" and self.jwt_secret_key == "dev-secret-change-me":
        raise RuntimeError("JWT_SECRET_KEY no configurado para producción")
    return self
```
Aplicar el mismo criterio a `database_url_admin` / `postgres_app_password`.

### C2. Sin rate limiting / bloqueo en `/auth/login` y flujos de contraseña
**Archivos:** `backend/app/services/auth_service.py:15` (`autenticar`), `routers/auth.py` (`/auth/login`, `/auth/refresh`, `/auth/cambiar-password-temporal`), `routers/usuarios.py` / `usuarios_empresas.py` / `mis_empresas.py` (los 3 endpoints de `resetear-password`).

Confirmado por las 4 auditorías independientes: no existe `slowapi` ni ninguna librería de rate limiting en `requirements.txt`, ni middleware custom, ni contador de intentos fallidos en el código.

**Escenario de explotación:** un atacante anónimo (sin ninguna cuenta) puede correr fuerza bruta o credential stuffing contra `/auth/login` sin límite de intentos, sin backoff, sin captcha, contra cualquier email conocido o adivinable. La política de password (mínimo 8 caracteres, sin exigencia de complejidad — ver B-baja) hace esto más viable, no menos.

**Fix recomendado:** `slowapi` (Redis-backed) o un contador simple en Postgres, con límite agresivo por IP + por email (ej. 5/min por IP, 5/15min por email) en los 5 endpoints listados arriba, con backoff exponencial y bloqueo temporal tras N fallos. Complementar con rate limiting de borde (nginx `limit_req` / Cloudflare) antes de que el tráfico llegue al backend.

---

## Hallazgos — ALTA

### A1. Dependencias con CVEs reales y activamente explotables (`pip-audit` ejecutado contra `requirements.txt`)

| Paquete | Actual | Fix | Por qué importa en ESTE proyecto |
|---|---|---|---|
| `python-multipart` | 0.0.20 | 0.0.31 | **Usado en producción real**: subida de logo (`PUT /empresas/actual/logo`) y de la plantilla Excel de migración (`POST .../migracion/confirmar`). Varias DoS por parsing malformado de `multipart/form-data` (preámbulo/epílogo sin límite, `Content-Length` negativo → lectura sin tope en memoria). Un atacante autenticado (o incluso no, según el endpoint) puede tumbar el proceso backend con una request craftada a mano. |
| `starlette` (transitiva de FastAPI 0.116.1) | 0.47.3 | ≥1.0.1 | Reconstrucción de `request.url` sin validar Host; `request.form()` ignora límites de campos/tamaño en `x-www-form-urlencoded` (DoS). |
| `PyJWT` | 2.9.0 | ≥2.12.0 | Impacto acotado aquí porque el proyecto fija `algorithms=["HS256"]` explícito y no usa JWK — igual conviene actualizar. |
| `weasyprint` | 62.3 | 68.0 | SSRF bypass en `default_url_fetcher` + inyección CSS. Bajo riesgo hoy (las plantillas no incluyen URLs de usuario), pero conviene actualizar. |
| `jinja2` | 3.1.5 | 3.1.6 | RCE vía `\|attr` en sandbox — plantillas son propias, no de usuario, riesgo bajo pero fix barato. |
| `python-dotenv` | 1.0.1 | 1.2.2 | Symlink traversal en `set_key()` — no se usa en runtime, riesgo bajo. |
| `pytest` | 8.3.4 | 9.0.3 | Solo relevante en CI/dev. |

Frontend (`npm audit --production`): `esbuild` 0.27.3–0.28.0 (lectura arbitraria de archivos en el dev server, no en build de producción) y `nanoid` &lt;3.3.18 (High, loop infinito con `size=0`) — ambas con fix vía `npm audit fix`, impacto bajo en producción (tooling de build, no runtime servido).

**Fix:** `pip install -U python-multipart starlette pyjwt weasyprint jinja2` (cuidado: revalidar el pin `pydyf==0.11.0` documentado en `requirements.txt` tras subir weasyprint) + `npm audit fix` en frontend. Priorizar `python-multipart` por ser el de mayor superficie expuesta.

### A2. Tokens JWT (access + refresh) en cookies legibles por JavaScript, sin `httpOnly`/`secure`
**Archivo:** `frontend/app/composables/useAuth.ts:40-41`
```ts
const accessToken = useCookie<string | null>('access_token', { sameSite: 'lax', default: () => null })
const refreshTokenCookie = useCookie<string | null>('refresh_token', { sameSite: 'lax', default: () => null })
```
`useCookie` del lado cliente no puede marcar `httpOnly` (eso solo se logra con `Set-Cookie` desde un servidor); confirmado que el backend nunca setea cookies — siempre devuelve los tokens en el body JSON.

**Consecuencia positiva de este diseño:** como no hay cookie que el browser adjunte automáticamente cross-site, **no aplica CSRF clásico** (cada request lleva `Authorization: Bearer` puesto a mano por JS) — esto reduce la urgencia de implementar tokens anti-CSRF.

**Consecuencia negativa:** cualquier XSS futuro en el SPA (hoy no se encontró ninguno explotable, pero el frontend no tiene CSP — ver A3) puede leer `document.cookie` y robar el refresh token, manteniendo sesión válida 7 días.

**Fix recomendado (rediseño, no urgente si se prioriza A3 primero):** mover el refresh token a una cookie `HttpOnly, Secure, SameSite=Strict` seteada por un endpoint server-side (Nitro), dejar el access token de vida corta solo en memoria. Mientras no se haga, mitigar reforzando CSP (A3) para reducir la probabilidad de XSS, y considerar acortar la vida del refresh token.

### A3. Cero headers de seguridad HTTP
**Archivo:** `backend/app/main.py:26-34` — solo `CORSMiddleware` montado. No hay CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`, ni en el backend ni en `frontend/nuxt.config.ts`.

**Riesgo:** clickjacking (sin `frame-ancestors`/`X-Frame-Options`), MIME-sniffing en PDFs/Excel servidos, sin CSP no hay mitigación de XSS en el SPA.

**Fix backend** (agregar en `main.py`):
```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
```
**Fix frontend:** como es SPA estática (`ssr:false`), estos headers deben agregarse en el reverse proxy que sirva el build (nginx `add_header ...`), no en `nuxt.config.ts`.

### A4. Docker: contenedores como root, sin compose de producción, Postgres expuesto a todas las interfaces
Tres hallazgos relacionados, todos bloqueantes antes de desplegar en un servidor real:

- **Sin `USER` en ningún Dockerfile** (`backend/Dockerfile`, `frontend/Dockerfile`) — los procesos corren como root dentro del contenedor. Fix: agregar `RUN useradd --create-home appuser` + `USER appuser`.
- **No existe ningún `docker-compose.prod.yml`** — el único compose (`docker-compose.yml`) corre `uvicorn --reload` (un solo proceso, sin `--workers`, flag de dev), `npm run dev` en frontend (dev server, no build optimizado), monta el código fuente como volumen, y no tiene `restart: unless-stopped` ni healthchecks para backend/frontend (solo `db` los tiene). Fix: crear un compose de producción con build multi-stage, sin bind-mounts de código, `gunicorn`+workers uvicorn o `--workers N`, `npm run build` + `node .output/server`, `restart: unless-stopped`, healthchecks en los 3 servicios.
- **Puerto de Postgres publicado sin acotar interfaz:** `docker-compose.yml` → `ports: ["${POSTGRES_PORT}:5432"]` publica en `0.0.0.0`, no solo loopback. Si este compose se reutiliza tal cual en un servidor con IP pública, Postgres queda alcanzable directo desde internet — combinado con C1 (credenciales dev reutilizadas por error), es acceso total a la BD sin pasar por RLS de aplicación. Fix: no publicar el puerto en producción (el backend ya lo alcanza por la red interna de Compose); si hace falta acceso puntual, `"127.0.0.1:${POSTGRES_PORT}:5432"` + túnel SSH.

### A5. Sin límite de tamaño en archivos subidos (DoS)
**Archivos:** `backend/app/routers/migracion.py:55-74`, `empresas.py:45-59` (logo), `empleados.py:59,93`, `ausencias.py:57`, `liquidaciones.py:89`, `planillas.py:74,101`.

Todos hacen `await archivo.read()` sin chequear tamaño antes. Solo se valida `content_type` (header controlado 100% por el cliente, fácilmente spoofeable) — ningún sniff de magic bytes real. Sin `client_max_body_size` a nivel de proxy tampoco (no hay reverse proxy en el repo).

**Escenario:** un usuario autenticado con permiso de subida (admin para logo/migración) sube un archivo de varios GB — el proceso backend (un solo worker sin `--workers`) agota memoria. El de migración además pasa por `openpyxl` (los `.xlsx` son ZIPs — riesgo de zip-bomb).

**Fix:** validar tamaño real antes de cargar completo en memoria (leer con tope: `archivo.read(MAX_BYTES + 1)` y rechazar si excede — ej. 5MB logo, 20MB Excel/documentos), agregar sniff de magic bytes (`python-magic`), y `client_max_body_size` en el reverse proxy como defensa en profundidad.

---

## Hallazgos — MEDIA

### M1. Recibo de pago individual: falta validar la planilla padre antes de acceder al movimiento (gap de autorización, hoy tapado por un efecto colateral frágil)
**Archivo:** `backend/app/routers/planillas.py:160-176` (`recibo_pago`) + `backend/app/services/planilla_service.py:133-142` (`obtener_movimiento`)

`obtener_movimiento` hace `movimientos_repo.get(db, movimiento_id)` — un `db.get()` directo **sin RLS**, porque `movimientos_planilla` no tiene RLS propio (confirmado en el comentario de la migración `0031`: "aislamiento transitivo vía join"). El comentario del código dice "RLS ya filtra por empresa", pero es falso para esta tabla. Este endpoint, a diferencia de `recibos_pago_zip` y `listar_movimientos`, **nunca llama primero a `obtener_planilla`** (que sí dispara RLS sobre `planillas`) — solo compara `movimiento.planilla_id != planilla_id`, dos valores que el propio atacante controla en la URL.

**Por qué no es Crítica hoy:** `reportes_service.armar_recibo_pago` sí hace `db.get(Planilla, ...)` después (con RLS+FORCE activo sobre `planillas`), y si el `planilla_id` no pertenece a la empresa del usuario, esa llamada devuelve `None` y la línea siguiente revienta con `AttributeError` → 500. Es decir: hoy no hay fuga de datos, pero por un efecto colateral de otra tabla, no por un control real de este endpoint. Es además un oráculo de existencia cross-tenant (200 vs 500 revela si el par de IDs existe en alguna empresa), y cualquier refactor futuro que evite tocar `planillas` reabriría una fuga completa de nómina de otra empresa.

**Fix:** en `recibo_pago` (`planillas.py:167`), llamar `planilla_service.obtener_planilla(db, planilla_id)` **antes** de `obtener_movimiento`, igual que ya hace `recibos_pago_zip`.

### M2. `movimientos_planilla` e `historial_salarial` sin RLS propio (defensa en profundidad incompleta)
Confirmado por ausencia en todas las migraciones de RLS y admitido explícitamente en `backend/alembic/versions/0031_rol_activo_rls_consulta.py:24-29`. El aislamiento de estas 2 tablas depende 100% de que cada código nuevo recuerde validar la tabla padre — ya se demostró frágil (M1).

**Fix:** agregar `empresa_id` (ya derivable vía `contrato_id`) + `ENABLE/FORCE ROW LEVEL SECURITY` + política de aislamiento a ambas tablas, igual que las otras 8 tablas operativas. Convierte cualquier futuro descuido en un simple 404, no en una fuga.

### M3. `/docs`, `/redoc`, `/openapi.json` expuestos sin restricción
**Archivo:** `backend/app/main.py:26` — `FastAPI(title=...)` sin `docs_url=None`/`redoc_url=None`/`openapi_url=None`. `settings.environment` existe en `config.py:16` pero no se usa en ningún lado del código (confirmado por grep).

**Riesgo:** con la API en internet, cualquiera sin autenticarse ve el esquema completo de endpoints, modelos y estructura interna (roles, nombres de tablas/campos) — reconocimiento gratis para un atacante.

**Fix:**
```python
app = FastAPI(
    title=...,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
```

### M4. Validación de archivos solo por `Content-Type` declarado (spoofable)
**Archivos:** `routers/empresas.py:52-56` (logo), `routers/migracion.py:23-28` (Excel). Mismo patrón que A5 pero enfocado en tipo, no tamaño: un admin podría subir un SVG con `<script>` embebido declarando `Content-Type: image/png`. Impacto acotado hoy porque el frontend consume el logo como blob en un `<img>` (no ejecuta scripts SVG) y el endpoint exige Bearer token (no cookie automática), pero sigue siendo contenido sin sanitizar almacenado en BD.

**Fix:** sniff de magic bytes real, o excluir `image/svg+xml` del set permitido de logos, o sanitizar el SVG (remover `<script>`/`on*=`) antes de guardar.

### M5. Sin logging de eventos de seguridad
Confirmado: cero `print()`/`logger.`/`logging.` en todo `backend/app`. No hay registro de intentos de login fallidos, resets de password, ni cambios de rol, más allá del access log HTTP default de uvicorn. (Nota positiva: como no hay logging custom, tampoco hay riesgo de fuga accidental de contraseñas en logs.)

**Fix:** logging estructurado en `auth_service.autenticar` (intentos fallidos con email/IP, nunca la contraseña) y en los 3 endpoints de reset — necesario para detectar ataques en curso e investigar incidentes.

### M6. Sin estrategia de backups de base de datos
No se encontró ningún script/cron/config de `pg_dump` ni WAL archiving en el repo. Es un hallazgo operacional, no de código, pero **bloqueante** antes de producción: sin backups, cualquier bug de migración, corrupción o ataque no tiene camino de recuperación.

**Fix:** `pg_dump` programado (cron externo o sidecar) con retención y prueba periódica de restauración, aislado de la app (para que un atacante con acceso a la app no pueda borrar también los backups).

---

## Hallazgos — BAJA

### B1. Password mínimo de 8 caracteres sin exigencia de complejidad
`backend/app/schemas/auth.py:27`, `schemas/usuarios_empresas.py:21`. No explotable solo, pero agrava C2 (fuerza bruta). Considerar longitud mayor o chequeo contra lista de contraseñas comunes.

### B2. CORS: `allow_credentials=True` + `allow_methods=["*"]`/`allow_headers=["*"]`, origins libres por env var
`backend/app/main.py:29-34`. No explotable hoy (Starlette rechaza wildcard real + `allow_credentials`, y no hay auth por cookie), pero `CORS_ALLOWED_ORIGINS` es un valor libre de `.env` sin validación — recordatorio operativo de mantenerlo curado en cada deploy.

### B3. Cookies del frontend sin `secure: true` explícito
`useAuth.ts:40-41` — depende de que Nuxt infiera `secure` del entorno; no confirmado. Fijarlo explícito evita que la cookie viaje en claro si algún día hay mixed-content por error.

### B4. Campos de texto libre sin `max_length`
`schemas/empleados.py` (`direccion`, `detalle_enfermedad`), `schemas/empresas.py` (`direccion`), `schemas/ausencias.py` (`certificado_ref`). Impacto bajo confirmado (Jinja2 autoescape activo, cero `v-html` en frontend) — solo higiene contra payloads desproporcionados.

### B5. Imágenes base de Docker con tag de major/minor version, no digest
`python:3.12-slim`, `node:22-alpine`, `postgres:16-alpine` — mejor que `latest`, pero no 100% reproducible. Mejora menor, no bloqueante.

### B6. HTTPS/HSTS depende 100% de infraestructura externa no incluida en el repo
No verificable en el código — normal para un repo de aplicación (el TLS lo termina un reverse proxy), pero confirmar que ese proxy exista en el plan de despliegue real antes de ir a producción.

---

## Verificado como correcto (no requiere acción, vale la pena confirmarlo explícito)

- **Hashing de contraseñas:** bcrypt vía `passlib`, sin rounds débiles.
- **JWT:** algoritmo fijo (`HS256`, sin `alg=none`), expiración correcta (15min access / 7 días refresh), rotación real de refresh tokens (single-use, JTI revocado en cada refresh).
- **Password temporal:** generada con `secrets.choice` (CSPRNG real), expira a las 24h verificado server-side.
- **Enumeración de usuarios:** mismo mensaje de error para usuario inexistente vs contraseña incorrecta.
- **`debe_cambiar_password`:** enforced server-side en `deps.py::get_usuario_actual` (whitelist de 3 rutas), no bypasseable desde el frontend.
- **Reset de contraseña y cambio de temporal:** revocan TODAS las sesiones previas del usuario (confirmado en código).
- **`empresa_id` nunca viaja en el body/query de escritura** — siempre sale del JWT o se valida contra BD en `/mis-empresas/*`.
- **RLS con `FORCE`,** rol de aplicación no-superusuario — las políticas se aplican en runtime, no es solo teatro.
- **Roles (`admin`/`contador`/`consulta`) aplicados de forma consistente** en prácticamente todos los endpoints de escritura revisados, con backstop adicional a nivel Postgres (políticas `RESTRICTIVE` que bloquean escritura del rol `consulta` en 11 tablas). *(Esto contradice — para bien — la nota del CLAUDE.md de que "el backend solo valida rol en 4 lugares"; esa nota quedó desactualizada, conviene corregirla.)*
- **Sin ruta de escalación de privilegios:** `usuarios_empresas` no acepta rol `"superadmin"`; `puede_crear_empresas`/`es_superadmin` no son delegables ni auto-otorgables.
- **Regla "empresa nunca sin admin"** y **autobloqueo self-service** (nadie resetea su propia password ni modifica su propio acceso) confirmados en código.
- **`.env` real nunca se filtró en el historial de git** (solo `.env.example` con placeholders, verificado con `git log --all --full-history`). `CREDENCIALES-DEV.txt` nunca existió en el historial.
- **Sin SQL injection:** ORM parametrizado en todo el backend; los `SET`/`set_config()` de RLS usan bind parameters, nunca f-string.
- **Sin command injection, SSRF, XXE:** cero coincidencias confirmadas por grep exhaustivo; no aplica XXE (no hay parsers XML).
- **Excel de migración:** `load_workbook(..., data_only=True)` — sin riesgo de formula injection.
- **Jinja2/WeasyPrint:** `autoescape=True` confirmado activo, sin `|safe`/`Markup` en ningún template.
- **Frontend:** cero usos de `v-html`/`innerHTML` en todo el proyecto.
- **Dependencias sin CVEs conocidos:** psycopg, sqlalchemy, fastapi, uvicorn, alembic, pydantic-settings, passlib, bcrypt, email-validator, httpx, openpyxl.

---

## Qué arreglar ANTES de exponer a internet (bloqueante) vs qué puede esperar

**Actualización 2026-08-26: los 8 puntos bloqueantes de la lista original ya están arreglados y verificados** (ver las tablas de estado de remediación arriba). Se deja la lista tal cual quedó redactada el día de la auditoría, como registro de lo que se pidió priorizar.

**Bloqueante (hacer antes de producción, todo de bajo costo):**
1. C1 — eliminar defaults inseguros de secretos/credenciales, forzar fallo de arranque si faltan.
2. C2 — rate limiting en login + endpoints de reset de contraseña.
3. A1 — actualizar `python-multipart` y `starlette` como mínimo (los demás del listado, en el mismo pase).
4. A3 — headers de seguridad HTTP (5 líneas de middleware).
5. A4 — compose de producción real (sin `--reload`, sin volumen de código, healthchecks, `restart`), contenedores sin root, Postgres no publicado a `0.0.0.0`.
6. A5 — límite de tamaño en subida de archivos.
7. M3 — deshabilitar `/docs`/`/openapi.json` en producción.
8. M6 — estrategia de backups (aunque sea un cron simple de `pg_dump` con retención, antes del primer usuario real).

**Puede esperar (hardening, no bloqueante para el lanzamiento):**
- A2 (rediseño de almacenamiento de tokens a cookie httpOnly) — mitigado en el corto plazo por A3 (CSP reduce probabilidad de XSS).
- M1/M2 (recibo IDOR-adjacent + RLS en movimientos_planilla) — real pero de explotación no trivial (requiere ya ser usuario autenticado de otra empresa + conocer IDs ajenos); arreglar en el próximo sprint, no en el día del lanzamiento.
- M4, M5, B1–B6.

## Secretos filtrados en código/historial de git
**No se encontró ninguno.** `.env` nunca fue trackeado, `.env.example` solo tiene placeholders, `CREDENCIALES-DEV.txt` nunca existió en el historial. El único punto relacionado es C1 (defaults inseguros en `config.py`, que SÍ están en el código pero son placeholders de desarrollo, no secretos reales filtrados) — no requiere limpieza de historial de git, solo el fix de código descrito arriba.

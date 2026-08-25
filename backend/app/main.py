from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import (
    auditoria,
    auth,
    ausencias,
    conceptos_variables_pendientes,
    contratos,
    decimo,
    empleados,
    empresas,
    health,
    horas_extra,
    liquidaciones,
    migracion,
    mis_empresas,
    planillas,
    tasas,
    usuarios,
    usuarios_empresas,
    vacaciones,
)

app = FastAPI(title="Nómina Panamá API")

# Auditoría de seguridad 2026-08-25 (hallazgo C2): /auth/login y compañía
# no tenían ningún límite de intentos -- ver routers/auth.py para los
# límites por endpoint.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def agregar_headers_de_seguridad(request, call_next):
    # Auditoría de seguridad 2026-08-25 (hallazgo A3): sin esto, la API no
    # mandaba ningún header de seguridad. HSTS es inofensivo servido por
    # HTTP en dev -- los navegadores solo lo respetan sobre HTTPS.
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(empleados.router)
app.include_router(contratos.router)
app.include_router(horas_extra.router)
app.include_router(conceptos_variables_pendientes.router)
app.include_router(planillas.router)
app.include_router(decimo.router)
app.include_router(vacaciones.router)
app.include_router(liquidaciones.router)
app.include_router(ausencias.router)
app.include_router(auditoria.router)
app.include_router(usuarios_empresas.router)
app.include_router(usuarios.router)
app.include_router(mis_empresas.router)
app.include_router(tasas.router)
app.include_router(migracion.router)

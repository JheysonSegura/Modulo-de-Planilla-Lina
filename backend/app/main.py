from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
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
    planillas,
    tasas,
    usuarios,
    usuarios_empresas,
    vacaciones,
)

app = FastAPI(title="Nómina Panamá API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(tasas.router)

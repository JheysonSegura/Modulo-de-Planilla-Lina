from fastapi import FastAPI

from app.routers import (
    auth,
    conceptos_variables_pendientes,
    contratos,
    decimo,
    empleados,
    empresas,
    health,
    horas_extra,
    liquidaciones,
    planillas,
    vacaciones,
)

app = FastAPI(title="Nómina Panamá API")

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

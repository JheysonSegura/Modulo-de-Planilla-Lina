from fastapi import FastAPI

from app.routers import auth, contratos, empleados, empresas, health

app = FastAPI(title="Nómina Panamá API")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(empleados.router)
app.include_router(contratos.router)

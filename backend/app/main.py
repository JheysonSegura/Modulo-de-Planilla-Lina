from fastapi import FastAPI

from app.routers import auth, empleados, health

app = FastAPI(title="Nómina Panamá API")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(empleados.router)

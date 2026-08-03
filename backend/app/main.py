from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Nómina Panamá API")

app.include_router(health.router)

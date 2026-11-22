from fastapi import APIRouter

from app.api.routes import buildings, files, health, layers, projects

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(files.router)
api_router.include_router(layers.router)
api_router.include_router(buildings.router)

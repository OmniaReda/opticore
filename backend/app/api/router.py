from fastapi import APIRouter

from app.api.routes import buildings, exports, files, health, layers, projects, survey, validation

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(files.router)
api_router.include_router(layers.router)
api_router.include_router(buildings.router)
api_router.include_router(survey.router)
api_router.include_router(validation.router)
api_router.include_router(exports.router)

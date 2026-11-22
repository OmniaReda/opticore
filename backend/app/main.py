from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.config import get_settings
from app.routers import files, layers, projects


def _operation_id(route: APIRoute) -> str:
    # Clean operationIds (e.g. "list_projects") → nice method names in the generated Angular client.
    return route.name


app = FastAPI(title="Opticore API", version="0.1.0", generate_unique_id_function=_operation_id)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(files.router)
app.include_router(layers.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}

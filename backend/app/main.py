"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.router import api_router
from app.config import get_settings
from app.db import get_engine
from app.errors import register_exception_handlers


def _operation_id(route: APIRoute) -> str:
    # Clean operationIds (e.g. "list_projects") → nice method names in the generated Angular client.
    return route.name


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    get_engine().dispose()  # close pooled DB connections on shutdown


def create_app() -> FastAPI:
    settings = get_settings()
    logging.getLogger("app").setLevel(settings.log_level)

    app = FastAPI(
        title="Opticore API",
        version="0.1.0",
        generate_unique_id_function=_operation_id,
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()

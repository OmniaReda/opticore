"""OpenAPI tweaks for the generated Angular client (ng-openapi-gen)."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _binary_uploads(node: Any) -> None:
    """FastAPI writes file uploads in OpenAPI 3.1 style (`contentMediaType`), which ng-openapi-gen turns
    into `string`. Rewrite them as `format: binary` so the client keeps `Blob` / `File` for uploads."""
    if isinstance(node, dict):
        if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
            del node["contentMediaType"]
            node["format"] = "binary"
        for value in node.values():
            _binary_uploads(value)
    elif isinstance(node, list):
        for value in node:
            _binary_uploads(value)


def install(app: FastAPI) -> None:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            _binary_uploads(schema)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]  # documented FastAPI extension point

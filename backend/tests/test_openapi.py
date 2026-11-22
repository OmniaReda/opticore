"""Contract with the generated Angular client (frontend: npm run api)."""

from app.main import app


def test_operation_ids_are_route_names() -> None:
    ops = {op["operationId"] for path in app.openapi()["paths"].values() for op in path.values()}
    assert {"list_projects", "upload_file", "process_file", "get_layers", "get_buildings", "health"} <= ops


def test_file_upload_is_binary() -> None:
    schemas = app.openapi()["components"]["schemas"]
    assert schemas["Body_upload_file"]["properties"]["file"] == {"type": "string", "format": "binary", "title": "File"}

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, ProjectDep
from app.services import exports

router = APIRouter(prefix="/projects/{project_id}/export", tags=["exports"])

KMZ = "application/vnd.google-earth.kmz"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DXF = "application/dxf"


def _file(content: bytes, media_type: str, filename: str) -> Response:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content, media_type=media_type, headers=headers)


@router.get("/kmz", response_class=Response, responses={200: {"content": {KMZ: {}}}})
def export_kmz(project: ProjectDep, db: DbSession) -> Response:
    """Boundary + buildings (coloured by review status, with IDs and survey users) for Google Earth."""
    return _file(exports.to_kmz(db, project), KMZ, "project.kmz")


@router.get("/xlsx", response_class=Response, responses={200: {"content": {XLSX: {}}}})
def export_xlsx(project: ProjectDep, db: DbSession) -> Response:
    """One row per building: IDs, review status, area, location, survey data."""
    return _file(exports.to_xlsx(db, project), XLSX, "buildings.xlsx")


@router.get("/dxf", response_class=Response, responses={200: {"content": {DXF: {}}}})
def export_dxf(project: ProjectDep, db: DbSession) -> Response:
    """Boundary + buildings + Building IDs in UTM 36N metres, one layer per review status (AutoCAD)."""
    return _file(exports.to_dxf(db, project), DXF, "project.dxf")

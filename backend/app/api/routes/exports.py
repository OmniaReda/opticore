from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, ProjectDep
from app.services import cad_map, exports, map_sheet, streets

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


@router.get(
    "/streets",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}}, 409: {"description": "No boundary yet"}, 502: {"description": "OSM down"}},
)
def export_streets(project: ProjectDep) -> Response:
    """Named streets inside the project boundary with their OpenStreetMap names (Arabic / English) and length."""
    return _file(streets.to_xlsx(project), XLSX, "streets.xlsx")


@router.get(
    "/survey-sheet",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}}, 409: {"description": "No drawing yet"}},
)
def export_survey_sheet(project: ProjectDep, db: DbSession) -> Response:
    """The whole map in the survey template: one row per Building ID with street name (survey, else nearest
    OpenStreetMap street), GPS, and every survey value known. Can be completed and uploaded back as the survey."""
    return _file(map_sheet.to_xlsx(db, project), XLSX, "survey-sheet.xlsx")


@router.get(
    "/street-map-dxf",
    response_class=Response,
    responses={200: {"content": {DXF: {}}}, 409: {"description": "No boundary yet"}, 502: {"description": "OSM down"}},
)
def export_street_map_dxf(project: ProjectDep, db: DbSession) -> Response:
    """AutoCAD street map in UTM 36N metres: boundary, OpenStreetMap streets with names, house numbers, field
    Floors / Total Users, and the drawing's buildings when there is a drawing. One layer each."""
    return _file(cad_map.to_dxf(db, project), DXF, "street-map.dxf")

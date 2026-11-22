from fastapi import APIRouter

from app.api.deps import DbSession, ProjectDep
from app.schemas import BuildingLayer
from app.services import buildings

router = APIRouter(prefix="/projects/{project_id}/buildings", tags=["buildings"])


@router.get("")
def get_buildings(project: ProjectDep, db: DbSession) -> BuildingLayer:
    """Buildings from the latest imported drawing, with review status (EPSG:4326 GeoJSON)."""
    return buildings.building_layer(db, project)

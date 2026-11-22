from fastapi import APIRouter

from app.api.deps import DbSession, ProjectDep
from app.schemas import ProjectLayers
from app.services import layers

router = APIRouter(prefix="/projects/{project_id}/layers", tags=["layers"])


@router.get("")
def get_layers(project: ProjectDep, db: DbSession) -> ProjectLayers:
    """Everything to draw on the project map: boundary + imported features (EPSG:4326 GeoJSON)."""
    return layers.project_layers(db, project)

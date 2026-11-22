import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo
from app.db import get_db
from app.models import ProjectFeature
from app.routers.projects import get_project_or_404
from app.schemas import BoundaryRead, FeatureRead, GeoJsonGeometry, ProjectLayers

router = APIRouter(prefix="/projects/{project_id}/layers", tags=["layers"])

Db = Annotated[Session, Depends(get_db)]


def _geojson(geom: BaseGeometry) -> GeoJsonGeometry:
    return GeoJsonGeometry.model_validate(mapping(geom))


@router.get("", response_model=ProjectLayers)
def get_layers(project_id: uuid.UUID, db: Db) -> ProjectLayers:
    """Everything to draw on the project map: boundary + imported features (EPSG:4326 GeoJSON)."""
    project = get_project_or_404(db, project_id)

    boundary = None
    if project.boundary is not None:
        shape = to_shape(project.boundary)
        boundary = BoundaryRead(geometry=_geojson(shape), source_file_id=project.boundary_file_id,
                                area_m2=round(geo.area_m2(shape), 1), perimeter_m=round(geo.length_m(shape), 1))

    rows = db.scalars(select(ProjectFeature).where(ProjectFeature.project_id == project_id))
    features = [FeatureRead(id=f.id, source_file_id=f.source_file_id, name=f.name, description=f.description,
                            geometry=_geojson(to_shape(f.geometry))) for f in rows]
    return ProjectLayers(boundary=boundary, features=features)

"""Map layers of a project: boundary + raw imported features (EPSG:4326 GeoJSON)."""

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo
from app.models import Project, ProjectFeature
from app.schemas import BoundaryRead, FeatureRead, ProjectLayers


def project_layers(db: Session, project: Project) -> ProjectLayers:
    boundary = None
    if project.boundary is not None:
        shape = to_shape(project.boundary)
        boundary = BoundaryRead(
            geometry=geo.to_geojson(shape),
            source_file_id=project.boundary_file_id,
            area_m2=round(geo.area_m2(shape), 1),
            perimeter_m=round(geo.length_m(shape), 1),
        )
    rows = db.scalars(select(ProjectFeature).where(ProjectFeature.project_id == project.id))
    features = [
        FeatureRead(
            id=f.id,
            source_file_id=f.source_file_id,
            name=f.name,
            description=f.description,
            geometry=geo.to_geojson(to_shape(f.geometry)),
        )
        for f in rows
    ]
    return ProjectLayers(boundary=boundary, features=features)

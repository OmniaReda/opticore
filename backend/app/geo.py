"""CRS helpers. Storage is EPSG:4326; every measurement is done in EPSG:32636 (UTM 36N, metres)."""

from pyproj import Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from app.schemas import GeoJsonGeometry

STORAGE_SRID = 4326
MEASURE_SRID = 32636  # WGS 84 / UTM zone 36N

_to_utm = Transformer.from_crs(STORAGE_SRID, MEASURE_SRID, always_xy=True).transform


def to_measure_crs(geom: BaseGeometry) -> BaseGeometry:
    """lon/lat (EPSG:4326) → UTM 36N metres. Never measure in degrees."""
    return transform(_to_utm, geom)


def area_m2(geom: BaseGeometry) -> float:
    return float(to_measure_crs(geom).area)


def length_m(geom: BaseGeometry) -> float:
    """Length of a line, or perimeter (boundary length) of a polygon, in metres."""
    utm = to_measure_crs(geom)
    return float(utm.boundary.length if utm.geom_type in ("Polygon", "MultiPolygon") else utm.length)


def to_geojson(geom: BaseGeometry) -> GeoJsonGeometry:
    """Shapely geometry (EPSG:4326) → API GeoJSON geometry."""
    return GeoJsonGeometry.model_validate(mapping(geom))

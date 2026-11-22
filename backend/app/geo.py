"""CRS helpers. Storage is EPSG:4326; every measurement is done in EPSG:32636 (UTM 36N, metres)."""
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

STORAGE_SRID = 4326
MEASURE_SRID = 32636  # WGS 84 / UTM zone 36N

_to_utm = Transformer.from_crs(STORAGE_SRID, MEASURE_SRID, always_xy=True).transform


def to_measure_crs(geom: BaseGeometry) -> BaseGeometry:
    """lon/lat (EPSG:4326) → UTM 36N metres. Never measure in degrees."""
    return transform(_to_utm, geom)


def area_m2(geom: BaseGeometry) -> float:
    return to_measure_crs(geom).area


def length_m(geom: BaseGeometry) -> float:
    """Length of a line, or perimeter (boundary length) of a polygon, in metres."""
    utm = to_measure_crs(geom)
    return utm.boundary.length if utm.geom_type in ("Polygon", "MultiPolygon") else utm.length

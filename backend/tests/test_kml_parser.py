import pytest

from app import geo
from app.importers import kml
from tests import kml_samples as s


def test_google_earth_kml() -> None:
    c = kml.parse_kml(s.GOOGLE_EARTH_KML)
    assert c.document_name == "منطقة تجريبية"
    assert [p.geometry.geom_type for p in c.placemarks] == ["Polygon", "Point"]
    poly, point = c.placemarks
    assert poly.name == "حدود المنطقة"
    assert point.name == s.POINT_NAME
    assert not poly.geometry.has_z and not point.geometry.has_z  # altitude dropped


def test_measurements_are_in_metres() -> None:
    poly = kml.parse_kml(s.GOOGLE_EARTH_KML).placemarks[0].geometry
    assert geo.area_m2(poly) == pytest.approx(s.RECT_AREA_M2, rel=1e-6)
    assert geo.length_m(poly) == pytest.approx(s.RECT_PERIMETER_M, rel=1e-6)


def test_cad_export_kml_without_namespace() -> None:
    c = kml.parse_kml(s.CAD_EXPORT_KML)
    assert [p.geometry.geom_type for p in c.placemarks] == ["LineString", "LineString"]
    assert {p.name for p in c.placemarks} == {"طبقة المباني"}
    assert c.placemarks[1].geometry.is_closed  # LinearRing kept as a closed line
    assert c.skipped == 1  # single-point line


def test_kmz() -> None:
    c = kml.load(s.kmz(s.GOOGLE_EARTH_KML), is_kmz=True)
    assert len(c.placemarks) == 2
    c = kml.load(s.kmz(s.GOOGLE_EARTH_KML, inner_name="other name.kml"), is_kmz=True)
    assert len(c.placemarks) == 2


@pytest.mark.parametrize(
    "data, is_kmz, message",
    [
        (b"not xml at all", False, "Not a valid KML"),
        (b"<?xml version='1.0'?><gpx/>", False, "root element is not <kml>"),
        (s.UTM_COORDS_KML, False, "out of lon/lat range"),
        (b"PK not really a zip", True, "Not a valid KMZ"),
    ],
)
def test_errors(data: bytes, is_kmz: bool, message: str) -> None:
    with pytest.raises(kml.KmlError, match=message):
        kml.load(data, is_kmz)


def test_kmz_without_kml() -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("image.png", b"x")
    with pytest.raises(kml.KmlError, match=r"no .kml"):
        kml.load(buf.getvalue(), is_kmz=True)


def test_external_entities_are_not_resolved() -> None:
    c = kml.parse_kml(s.XXE_KML)
    assert c.placemarks[0].name is None or "[fonts]" not in c.placemarks[0].name

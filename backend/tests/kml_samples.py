"""SAMPLE KML files for tests — synthetic, not customer data.

The boundary is an exact 200 m × 300 m rectangle built in UTM 36N and converted to lon/lat,
so its area (60,000 m²) and perimeter (1,000 m) are known independently of the code under test.
"""

import io
import zipfile

from pyproj import Transformer

_to_wgs = Transformer.from_crs(32636, 4326, always_xy=True).transform

_X0, _Y0 = 336_000.0, 3_331_000.0  # somewhere in UTM 36N
RECT_UTM = [(_X0, _Y0), (_X0 + 200, _Y0), (_X0 + 200, _Y0 + 300), (_X0, _Y0 + 300), (_X0, _Y0)]
RECT_AREA_M2 = 200 * 300
RECT_PERIMETER_M = 2 * (200 + 300)


def _lonlat(points: list[tuple[float, float]], z: str = ",0") -> str:
    return " ".join(f"{lon:.10f},{lat:.10f}{z}" for lon, lat in (_to_wgs(x, y) for x, y in points))


POINT_NAME = "نقطة ملاحظة تجريبية 1&2"

# Google Earth style: namespace, gx:CascadingStyle, Z values, LookAt, Arabic names.
GOOGLE_EARTH_KML = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2"
     xmlns:kml="http://www.opengis.net/kml/2.2">
<Document>
  <name>منطقة تجريبية</name>
  <gx:CascadingStyle kml:id="s1"><Style><LineStyle><width>3</width></LineStyle></Style></gx:CascadingStyle>
  <Placemark>
    <name>حدود المنطقة</name>
    <LookAt><longitude>31.3</longitude><latitude>30.1</latitude><altitude>17</altitude></LookAt>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>
      {_lonlat(RECT_UTM)}
    </coordinates></LinearRing></outerBoundaryIs></Polygon>
  </Placemark>
  <Placemark>
    <name>{POINT_NAME.replace("&", "&amp;")}</name>
    <Point><coordinates>{_lonlat([(_X0 + 100, _Y0 + 150)], z=",20.9")}</coordinates></Point>
  </Placemark>
</Document>
</kml>
""".encode()

_SMALL_RING = [(_X0, _Y0), (_X0 + 5, _Y0), (_X0 + 5, _Y0 + 5), (_X0, _Y0)]

# CAD-Earth style: no namespace, lines in MultiGeometry, one degenerate line, no polygon.
CAD_EXPORT_KML = f"""<?xml version="1.0" standalone="yes"?>
<kml><Document><name>export.dwg</name><Folder><name>Layers</name>
<Placemark><name>طبقة المباني</name><MultiGeometry>
  <LineString><coordinates>{_lonlat([(_X0, _Y0), (_X0 + 10, _Y0)], z="")}</coordinates></LineString>
  <LinearRing><coordinates>{_lonlat(_SMALL_RING, z="")}</coordinates></LinearRing>
  <LineString><coordinates>{_lonlat([(_X0, _Y0)], z="")}</coordinates></LineString>
</MultiGeometry></Placemark>
</Folder></Document></kml>
""".encode()

# Self-intersecting "bow-tie" boundary.
_BOWTIE = [(_X0, _Y0), (_X0 + 100, _Y0 + 100), (_X0 + 100, _Y0), (_X0, _Y0 + 100), (_X0, _Y0)]
INVALID_POLYGON_KML = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>bad</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>{_lonlat(_BOWTIE)}</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document></kml>
""".encode()

EMPTY_KML = b'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>'

UTM_COORDS_KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
<Point><coordinates>336000,3331000</coordinates></Point></Placemark></Document></kml>"""

XXE_KML = b"""<?xml version="1.0"?>
<!DOCTYPE kml [<!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">]>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>&xxe;</name>
<Point><coordinates>31.3,30.1</coordinates></Point></Placemark></Document></kml>"""


def kmz(kml: bytes, inner_name: str = "doc.kml") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("files/readme.txt", "sample")
        zf.writestr(inner_name, kml)
    return buf.getvalue()

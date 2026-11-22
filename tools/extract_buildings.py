"""Prototype: extract building polygons + Building IDs from a Design Team DXF.

Usage:
    python tools/extract_buildings.py data/<project>.dxf [--out data/<project>_buildings.geojson]

DWG files must be converted to DXF first, e.g. with LibreDWG:
    dwg2dxf -y -o data/<project>.dxf "data/<project>.dwg"

Output GeoJSON is in EPSG:4326. Each feature has:
    status: "ok" | "multiple_ids" | "no_id"
    building_ids: list of IDs found inside the polygon
    area_m2: area measured in EPSG:32636
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass

import ezdxf
from pyproj import Transformer
from shapely.geometry import LineString, Point, mapping
from shapely.ops import polygonize, transform, unary_union
from shapely.strtree import STRtree

BUILDING_LAYER = "مناطق سكنيه"
ID_LAYER = "Serial Home"
ID_PATTERN = re.compile(r"^\s*ERA\s*(\d+)\s*$")
MIN_POLYGON_AREA_M2 = 5.0
SOURCE_CRS = 32636  # WGS 84 / UTM zone 36N (Design Team CAD)


@dataclass
class Label:
    building_id: str
    point: Point


def read_building_lines(msp) -> list[LineString]:
    lines = []
    for e in msp.query(f'LWPOLYLINE[layer=="{BUILDING_LAYER}"]'):
        pts = [tuple(p) for p in e.get_points("xy")]
        if e.closed and pts:
            pts.append(pts[0])
        if len(set(pts)) >= 2:
            lines.append(LineString(pts))
    return lines


def read_labels(msp) -> list[Label]:
    labels = []
    for e in msp.query(f'TEXT[layer=="{ID_LAYER}"]'):
        m = ID_PATTERN.match(e.dxf.text)
        if m:
            labels.append(Label(f"ERA {int(m.group(1))}", Point(e.dxf.insert[0], e.dxf.insert[1])))
    return labels


def extract(dxf_path: str):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    polys = [p for p in polygonize(unary_union(read_building_lines(msp))) if p.area > MIN_POLYGON_AREA_M2]
    labels = read_labels(msp)

    tree = STRtree(polys)
    ids_by_poly: dict[int, list[str]] = defaultdict(list)
    orphan_labels: list[Label] = []
    for lab in labels:
        idx = tree.query(lab.point, predicate="within")
        if len(idx):
            ids_by_poly[int(idx[0])].append(lab.building_id)
        else:
            orphan_labels.append(lab)
    return polys, ids_by_poly, orphan_labels


def to_geojson(polys, ids_by_poly, orphan_labels) -> dict:
    to_wgs = Transformer.from_crs(SOURCE_CRS, 4326, always_xy=True).transform
    features = []
    for i, p in enumerate(polys):
        ids = ids_by_poly.get(i, [])
        status = "ok" if len(ids) == 1 else ("no_id" if not ids else "multiple_ids")
        features.append({
            "type": "Feature",
            "geometry": mapping(transform(to_wgs, p)),
            "properties": {"status": status, "building_ids": ids, "area_m2": round(p.area, 1)},
        })
    for lab in orphan_labels:
        features.append({
            "type": "Feature",
            "geometry": mapping(transform(to_wgs, lab.point)),
            "properties": {"status": "id_outside_polygon", "building_ids": [lab.building_id]},
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    polys, ids_by_poly, orphans = extract(args.dxf)
    one = sum(len(v) == 1 for v in ids_by_poly.values())
    many = sum(len(v) > 1 for v in ids_by_poly.values())
    print(f"polygons: {len(polys)}")
    print(f"  with exactly 1 ID : {one}")
    print(f"  with several IDs  : {many}")
    print(f"  without ID        : {len(polys) - len(ids_by_poly)}")
    print(f"IDs outside any polygon: {len(orphans)}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(to_geojson(polys, ids_by_poly, orphans), f, ensure_ascii=False)
        print(f"written {args.out}")


if __name__ == "__main__":
    main()

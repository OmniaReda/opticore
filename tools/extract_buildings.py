"""Command-line check of building extraction from a Design Team DXF (same code as the backend importer).

Usage (from the repo root, with the backend virtualenv):
    backend/.venv/Scripts/python tools/extract_buildings.py data/<project>.dxf [--out <file>.geojson]

DWG files must be converted to DXF first, e.g. with LibreDWG:
    dwg2dxf -y -o data/<project>.dxf "data/<project>.dwg"

Layer names and the Building ID format come from backend/app/rules/cad_layers.yaml (profile auto-detected).
Output GeoJSON is in EPSG:4326. Each feature has:
    status: "ok" | "multiple_ids" | "no_id" | "id_outside_polygon"
    building_ids: list of IDs found inside the polygon
    area_m2: area measured in EPSG:32636
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pyproj import Transformer  # noqa: E402
from shapely.geometry import mapping  # noqa: E402
from shapely.ops import transform  # noqa: E402

from app import rules  # noqa: E402
from app.importers import cad  # noqa: E402


def to_geojson(result: cad.CadBuildings) -> dict:
    to_wgs = Transformer.from_crs(32636, 4326, always_xy=True).transform
    ids_by_poly: dict[int, list[str]] = defaultdict(list)
    for lab in result.labels:
        if lab.building_index is not None:
            ids_by_poly[lab.building_index].append(lab.building_id)
    features = []
    for i, p in enumerate(result.polygons):
        ids = ids_by_poly.get(i, [])
        status = "ok" if len(ids) == 1 else ("no_id" if not ids else "multiple_ids")
        features.append({"type": "Feature", "geometry": mapping(transform(to_wgs, p)),
                         "properties": {"status": status, "building_ids": ids, "area_m2": round(p.area, 1)}})
    for lab in result.labels:
        if lab.building_index is None:
            features.append({"type": "Feature", "geometry": mapping(transform(to_wgs, lab.point)),
                             "properties": {"status": "id_outside_polygon", "building_ids": [lab.building_id]}})
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    result = cad.extract(cad.read_dxf(Path(args.dxf)), rules.cad_layers())
    counts: dict[int, int] = defaultdict(int)
    for lab in result.labels:
        if lab.building_index is not None:
            counts[lab.building_index] += 1
    print(f"profile: {result.profile.name}")
    print(f"polygons: {len(result.polygons)}")
    print(f"  with exactly 1 ID : {sum(n == 1 for n in counts.values())}")
    print(f"  with several IDs  : {sum(n > 1 for n in counts.values())}")
    print(f"  without ID        : {len(result.polygons) - len(counts)}")
    print(f"IDs outside any polygon: {sum(lab.building_index is None for lab in result.labels)}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(to_geojson(result), f, ensure_ascii=False)
        print(f"written {args.out}")


if __name__ == "__main__":
    main()

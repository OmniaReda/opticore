"""DXF/DWG upload → background processing → buildings + Building IDs with review status."""

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.importers import dwg
from app.rules import CadLayerRules
from tests import cad_samples as cs
from tests import kml_samples as ks
from tests.test_kml_import import file_state, new_project, upload


def buildings(client: TestClient, pid: str) -> dict[str, Any]:
    r = client.get(f"/projects/{pid}/buildings")
    assert r.status_code == 200, r.text
    return r.json()


def by_code(layer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {",".join(b["codes"]): b for b in layer["buildings"]}


def test_dxf_buildings_and_review_status(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "رسم المباني.dxf", cs.drawing())

    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert state["note"] == (
        "Layers: validated_drawing · 6 buildings: 4 with 1 ID, 1 with several IDs, 1 without ID"
        " · 1 IDs outside any building · 1 unreadable ID labels"
    )

    layer = buildings(client, pid)
    assert layer["source_file_id"] == f["id"]
    assert layer["provisional"] is True  # rules file is status: TBC
    assert layer["summary"] == {
        "total": 6,
        "ok": 4,
        "multiple_ids": 1,
        "no_id": 1,
        "orphan_ids": 1,
        "inside": None,
        "crossing": None,
        "outside": None,
    }  # no boundary yet
    b = by_code(layer)
    assert set(b) == {"1", "2", "3,3-2", "5", "6", ""}
    assert b["1"]["status"] == "ok"
    assert b["2"]["status"] == "ok"  # rebuilt from open lines
    assert b["3,3-2"]["status"] == "multiple_ids"
    assert b[""]["status"] == "no_id"
    assert b["1"]["area_m2"] == pytest.approx(200, abs=0.5)  # measured in UTM 36N
    assert b["3,3-2"]["area_m2"] == pytest.approx(300, abs=0.5)
    assert b["1"]["geometry"]["type"] == "Polygon"
    lon, lat = b["1"]["geometry"]["coordinates"][0][0]
    assert 31 < lon < 32 and 29 < lat < 31  # stored as lon/lat, 2D
    assert [o["code"] for o in layer["orphan_labels"]] == ["9"]
    # Sorted by Building ID; buildings without ID last.
    assert [",".join(x["codes"]) for x in layer["buildings"]] == ["1", "2", "3,3-2", "5", "6", ""]


def test_boundary_position(client: TestClient) -> None:
    pid = new_project(client)
    upload(client, pid, "boundary.kml", ks.GOOGLE_EARTH_KML)  # 200 m × 300 m around the drawing origin
    upload(client, pid, "drawing.dxf", cs.drawing())
    layer = buildings(client, pid)
    assert (layer["summary"]["inside"], layer["summary"]["crossing"], layer["summary"]["outside"]) == (4, 1, 1)
    b = by_code(layer)
    assert b["5"]["boundary_position"] == "crossing"
    assert b["6"]["boundary_position"] == "outside"  # kept, not dropped: the Design Team numbers these too
    assert b["1"]["boundary_position"] == "inside"


def test_base_drawing_profile(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "base.dxf", cs.base_drawing())
    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert state["note"].startswith("Layers: base_drawing")
    assert "2 unreadable ID labels" in state["note"]  # 'note' and 'ERA 3-2'
    b = by_code(buildings(client, pid))
    assert {"1", "2", "3", "5", "6"} <= set(b)  # 'ERA 1' → '1'


def test_new_drawing_replaces_buildings(client: TestClient) -> None:
    pid = new_project(client)
    first = upload(client, pid, "v1.dxf", cs.base_drawing())
    second = upload(client, pid, "v3.dxf", cs.drawing())
    assert "replaced buildings from a previous drawing" in file_state(client, pid, second["id"])["note"]
    layer = buildings(client, pid)
    assert layer["source_file_id"] == second["id"]
    assert layer["summary"]["total"] == 6

    # Deleting the first drawing does not touch the current buildings; deleting the current one clears them.
    client.delete(f"/projects/{pid}/files/{first['id']}")
    assert buildings(client, pid)["summary"]["total"] == 6
    client.delete(f"/projects/{pid}/files/{second['id']}")
    layer = buildings(client, pid)
    assert layer["summary"]["total"] == 0 and layer["orphan_labels"] == [] and layer["source_file_id"] is None


def test_reprocess_dxf(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "a.dxf", cs.drawing())
    r = client.post(f"/projects/{pid}/files/{f['id']}/process")
    assert r.status_code == 202, r.text
    assert file_state(client, pid, f["id"])["status"] == "processed"
    assert buildings(client, pid)["summary"]["total"] == 6  # not duplicated


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (cs.unknown_layers_drawing(), "No known building/ID layers in this drawing"),
        (cs.local_coordinates_drawing(), "do not look like UTM zone 36N metres"),
        (b"this is not a drawing", "Not a readable DXF file"),
    ],
)
def test_bad_drawings_fail_with_clear_message(client: TestClient, content: bytes, message: str) -> None:
    pid = new_project(client)
    f = upload(client, pid, "bad.dxf", content)
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert message in state["error"]
    assert buildings(client, pid)["summary"]["total"] == 0


def test_unknown_layers_message_lists_found_layers(client: TestClient) -> None:
    pid = new_project(client)
    f = upload(client, pid, "bad.dxf", cs.unknown_layers_drawing())
    assert "walls" in file_state(client, pid, f["id"])["error"]


# --- DWG: conversion with the external converter (replaced by a fake script in tests) ---

FAKE_CONVERTER = """
import shutil, sys
args = sys.argv[1:]
if args[0] == "fail":
    sys.stderr.write("Warning: something\\nERROR: bad section\\n")
    sys.exit(1)
shutil.copyfile(args[-1], args[args.index("-o") + 1])  # the 'DWG' in tests already holds DXF content
"""


@pytest.fixture
def fake_converter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    script = tmp_path / "fake_dwg2dxf.py"
    script.write_text(FAKE_CONVERTER, encoding="utf-8")
    mode: list[str] = ["ok"]
    monkeypatch.setattr(get_settings(), "dwg2dxf_path", Path(sys.executable))
    monkeypatch.setattr(
        dwg, "build_argv", lambda exe, src, dst: [str(exe), str(script), mode[0], "-o", str(dst), str(src)]
    )
    return mode


def test_dwg_without_converter(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "dwg2dxf_path", None)
    pid = new_project(client)
    f = upload(client, pid, "drawing.dwg", cs.drawing())
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert "OPTICORE_DWG2DXF_PATH" in state["error"]


def test_dwg_converted_and_imported(client: TestClient, fake_converter: list[str]) -> None:
    pid = new_project(client)
    f = upload(client, pid, "رسم.dwg", cs.drawing())
    state = file_state(client, pid, f["id"])
    assert state["status"] == "processed", state
    assert "converted with" in state["note"]
    assert buildings(client, pid)["summary"]["total"] == 6


def test_dwg_conversion_failure(client: TestClient, fake_converter: list[str]) -> None:
    fake_converter[0] = "fail"
    pid = new_project(client)
    f = upload(client, pid, "broken.dwg", b"not really a dwg")
    state = file_state(client, pid, f["id"])
    assert state["status"] == "failed"
    assert state["error"] == "DWG conversion failed (exit code 1): ERROR: bad section"


# --- rules file ---


def test_rules_file_requires_metadata_and_capture_group() -> None:
    base: dict[str, Any] = {
        "source": "test",
        "approved_by": None,
        "status": "TBC",
        "min_building_area_m2": 5,
        "profiles": [{"name": "p", "building_layer": "b", "id_layer": "i", "id_pattern": r"^(\d+)$"}],
    }
    assert CadLayerRules.model_validate(base).provisional is True
    for broken in (
        {**base, "status": "maybe"},
        {k: v for k, v in base.items() if k != "source"},
        {**base, "profiles": [{**base["profiles"][0], "id_pattern": r"^\d+$"}]},
    ):
        with pytest.raises(ValueError):
            CadLayerRules.model_validate(broken)

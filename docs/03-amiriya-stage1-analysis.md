# Reference project: Al-Amiriya (الاميرية) — Stage 01 files

## Stage 01 input
`الاميرية ftth.kml` (exported from Google Earth Web)
- 1 Polygon "الاميرية 2026" — project boundary, 20 vertices, valid. Area ≈ 36.1 ha, perimeter ≈ 4.7 km.
- 1 Point note: "يوجد داخل هذه المنطقة ام سان 80&13 تم احلالهم ftth" (MSAN cabinets 80 & 13 replaced by FTTH).
- Parser notes: ignore `gx:CascadingStyle` styles; drop altitude; Arabic names.

## Stage 01 outputs
### `CAD الاميرية V1 11-10.dwg`
- Format AC1024 (AutoCAD 2010). Units metres. Coordinates **UTM 36N (EPSG:32636)**.
- Layers / entities:
  | Layer | Content | Count |
  |---|---|---|
  | `مناطق سكنيه` | Building outlines, LWPOLYLINE (only 24 closed) | 1,103 |
  | `Serial Home` | TEXT `ERA <n>`, height 1.0 | 857 (ERA 0–856, no gaps, no duplicates) |
  | `TEXT نص الدلتا 4-4` | Street/lane names, style `x` = font `xarb.shx` (legacy, non-Unicode) | 73 TEXT + 1 MTEXT |
  | `baldimg` | 2 HATCH + 1 polyline (red area in plots) — meaning TBC | 3 |
  | `0` | Project boundary + 2 points | — |
  | `500`, `2500`, `1-500` | Print frames / block `dddfffff` | — |
- One INSERT (layer `500`) located far outside the project (x≈103,365) → clip to boundary on import.

### `KMZ الاميرية V1 7-10.kml` (CAD-Earth export)
- Only line geometry: placemark `مناطق سكنيه` (1,061 LineString + 42 LinearRing) and boundary on layer `0`.
- No IDs, no street names, no hatch.
- **Dated 7-10 while DWG is 11-10** → may be out of sync.

### PDFs
- `General … V1 11-10` — 1 × A0 overview plot (AutoCAD).
- `CAD … V1 11-10 Frame_5` — 5 × A0 survey sheets (frames), surroundings hatched red.

## Automatic extraction test (tools/extract_buildings.py)
polygonize(building lines) + point-in-polygon on `ERA` labels:

| Result | Count |
|---|---|
| Polygon with exactly 1 ID | 658 (77%) |
| Polygon with several IDs (missing dividing line) | 84 |
| Polygon without ID (courtyards/gaps) | 113 |
| ID outside any polygon | 14 |

![extraction](amiriya_auto_extraction.png)

→ ~3/4 of Stage 03 polygon work can be automated; the rest becomes a review screen.

---

# Stage 02–03 files (received 2026-11-22)

## Stage 02 — field survey
- Phone photos of the printed A0 survey sheets, marked up by hand (floors × units, C/V, entrance, notes), plus RAR archives of scans.
- Not machine-readable → stays offline (as planned). The result of this stage is typed into the survey Excel in Stage 03.

## Stage 03 output — validated drawing `CAD … V3 3-11.dwg`
- Buildings layer renamed to **`Building`** (1,319 LWPOLYLINE, only 18 closed). Final IDs on **`Serial HomeNEW`**: 945 TEXT, e.g. `12`, `12-2`, `407-1`.
- Old layer `Serial Home` is still there (857 plain numbers, no `ERA` prefix).
- Survey data is also drawn as text: `place mark` (= Excel `Placemark ID`), `TOTAL`, `Core-Void`, `NUM Building`, `Name Building`, `Comment`, `Entrance length of the house`, plus `22_Entrance` (931 entrance blocks) and an `FTTH` hatch.
- Automatic extraction (polygonize + point-in-polygon, profile `validated_drawing`):

| Result | V1 base drawing | V3 validated drawing |
|---|---|---|
| Polygons | 855 | 921 |
| Exactly 1 ID | 658 (77 %) | 810 (88 %) |
| Several IDs | 84 | 55 |
| No ID | 113 | 56 |
| ID outside any polygon | 14 | 7 |

- Against the project boundary (V1): 791 buildings inside, 56 crossing (58 IDs), 8 outside (7 IDs, 7–31 m away). The Design Team does **not** clip to the boundary. All 14 orphan IDs are inside the boundary, so they come from drawing gaps, not from being out of area.
- The layer-`0` polyline in the drawing is identical to the KML boundary (IoU 1.0).

## Stage 03 output — survey Excel `Survey_… 3-11 final.xlsx` (template v1.1)
- Sheets: `Survey` (945 rows × 32 columns), `Daily` (per-day progress), `Settings`, `Lists` (allowed values).
- Columns (header names, row 1): ID (unique), Visit Date, Exchange, Company, Surveyor Name, Sector, Part, Street Name, Building Entrance Length (m), Building Name, Building Number, Building GPS N, Building GPS E, Floors (excl. GF), Users per Floor (excl. GF), GF Users (incl. shops), Total Users, HPs "TE Required to be added", Comments, Sub Category, Final Category, Placemark ID, Entrance Marked (Y/N), MSAN Note, Void / Core, HP Count / Not Count, QTY of Home Pass, TE Comment, TE Rep Name, Approval Status, Sign-off Date, QC Flags (auto).
- `Company` = `ERA` on every row → **`ERA` is the survey company, not part of the Building ID.**
- IDs: 945 unique. They match the V3 `Serial HomeNEW` labels **1 : 1**.
- GPS vs CAD label position: median 2 m, 90th percentile 7 m. **3 rows are more than 50 m away** (up to 241 m), which is a real QC finding.
- `Total Users = Floors × Users per Floor + GF Users` holds for 672 of 673 complete rows.
- Decision columns: `HP Count / Not Count` (693 Count, 41 Not Count, 19 Review), `TE Comment` (866 OK, 70 Delete), `Void / Core` (502 Core, 157 Void).
- Contains personal names (surveyors, TE representatives) → local only, never in tests, fixtures or commits.

## Design drawing `Secondary - … - Zone e.dwg` (other region, ~26.28° N)
- The first real **Stage 04 design** example, from a different project. AC1032; LibreDWG converts it with 70 ATTRIB errors (exit 0).
- `09_HUB BOX`: 43 × block `Hub Box 8 port`, attribute `HUBNAME` (e.g. `1-1/1/8`). `18_Hub Boundary`: Hub service-area outlines.
- Network boxes: 1,204 inserts on layers `01-L1` … `06-L6` (blocks `11S1..3` = "ZTE 11P", `9ES1..4` = "ZTE 9P", `10S4` = "ZTE 10P"). Median 29 boxes per Hub, maximum 43.
- Every box has a label `<hub>-L<n>-<type>-B<n>-<len>m-<pos>`, e.g. `1-1/1/8-L1-11S2-B2-60m-GF`. All 1,204 parse with one pattern. Sum of `<len>` is 48.6 km.
- Cables: LWPOLYLINE on the same `0n-Ln` layers. Civil works: `24_Trench`, `25_Pipe` (`1 HDPE 32/29`), `15_tension clamp`.
- Meaning of these conventions is TBC (see docs/04).

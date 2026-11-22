# OPTICORE — AI-Powered FTTH/ODN Design Platform

Read this file fully before any task. Detailed background is in `docs/`.

## What we are building
A web platform that replaces the Design Team's manual FTTH/ODN design workflow (AutoCAD + ArcGIS Pro + Excel):
import project files → validate buildings & survey data → generate network design (service areas, Hubs, network boxes, cable routes) → cable lengths + quantity sheets → export (Excel / KMZ / DXF).

**Current phase: PROTOTYPE** (~2 weeks, solo developer + Claude Code). Not the full MVP. See `docs/01-plan-and-scope.md`.

## Team & working mode
- One developer (Omnia, Senior Angular developer) + Claude Code. No other engineers.
- Omnia is strong in Angular, RxJS, reactive forms, NgBootstrap, ABP. Newer to Python, GIS and FTTH — explain GIS/Python decisions briefly in PRs.
- Domain rules come from the Design Team (FTTH engineers). **Never invent engineering values.** Unknown values go in config, marked `TBC` (To Be Confirmed), and are shown as "provisional" in the UI.

## Stack
| Layer | Choice |
|---|---|
| Frontend | Angular (standalone components, latest LTS), RxJS, NgBootstrap, **OpenLayers** for maps |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| DB | PostgreSQL 16 + PostGIS (docker-compose) |
| Geo libs | shapely, pyproj, ezdxf (DXF), openpyxl (Excel), simplekml / lxml (KML) |
| DWG | Not read directly. Convert DWG → DXF first (LibreDWG `dwg2dxf` or ODA File Converter). Licensing of DWG SDKs is an open decision. |
| Jobs | FastAPI BackgroundTasks for the prototype (no queue yet) |
| API client | Generated from FastAPI OpenAPI spec (`ng-openapi-gen`), like ABP proxy generation |

## Geospatial invariants (do not break)
- **Storage CRS: EPSG:4326** (lon/lat) in PostGIS `geometry(..., 4326)`.
- **All measurements (length, area, distance) in EPSG:32636 (WGS 84 / UTM zone 36N), metres.** Never measure in degrees.
- Design Team CAD files are in **UTM 36N metres** (header says `$INSUNITS = 1`, which is wrong — ignore it). KML/KMZ are EPSG:4326.
- 2D only — drop Z/altitude on import.
- Cable length = designed route geometry length. **No automatic wastage/slack** unless an approved rule says otherwise.
- All text is UTF-8 end-to-end (Arabic project/street names).

## Domain vocabulary (use the Design Team's terms in UI)
- **Hub** (not FDH), **Network Box** (types TBC), **Service Area**, **Building ID** (e.g. `12`, `12-2` as in the survey Excel; base drawings write it as `ERA 12` — `ERA` is the survey company, not part of the ID). Format/pattern lives in `backend/app/rules/cad_layers.yaml`.
- Survey fields per building: Building ID, Street Name, Building Number, Floors, Apartments per Floor, Shops, Total Users, Latitude, Longitude.
- Workflow has 7 stages — see `docs/02-design-team-workflow.md`.

## Known CAD file structure (test region files)
See `docs/03-amiriya-stage1-analysis.md`. Layer names differ between drawing versions → each convention is a profile in `backend/app/rules/cad_layers.yaml` (auto-detected). Stage 01 base drawing:
- Buildings layer `مناطق سكنيه`: LWPOLYLINEs, **mostly open** → build polygons with `shapely.ops.polygonize`.
- Building IDs layer `Serial Home`: TEXT `ERA <n>` → link to polygons by point-in-polygon.
- Street names layer `TEXT نص الدلتا 4-4`: TEXT in legacy SHX font `xarb.shx` → **not Unicode**, decoding is an open issue.
- Hatch layer `baldimg`: meaning TBC. Frame layers `500`, `2500`, `1-500`: print frames, ignore for design.
- One stray INSERT far outside the project extent (frame layer, not read).
- Stage 03 validated drawing: buildings on `Building`, IDs on `Serial HomeNEW` (match the survey Excel 1:1).
- Buildings are **not** clipped to the project boundary (the Design Team numbers edge buildings too); each building gets inside/crossing/outside instead.
- `$INSUNITS` is unreliable (files say 1 = inches but are metres) → do not trust it; check coordinates look like UTM 36N instead.

## Repository layout
```
backend/   FastAPI app (app/), tests/, alembic migrations
frontend/  Angular app (create with: ng new frontend --standalone --routing --style=scss)
tools/     standalone scripts/prototypes (e.g. building extraction)
docs/      requirements, analysis, decisions (ADR), open questions
data/      LOCAL ONLY — customer files (DWG/KML/PDF/Excel). Git-ignored. Never commit.
```

## Commands
```bash
docker compose up -d db                       # PostGIS on localhost:5432
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
alembic upgrade head                          # apply DB migrations
uvicorn app.main:app --reload                 # API on :8000, docs on /docs
pytest                                        # backend tests (real PostGIS, DB "opticore_test")
python tools/extract_buildings.py data/<file>.dxf   # building extraction prototype
cd frontend && npm start                      # Angular on :4200, proxies /api → :8000
npm run api                                   # regenerate src/app/api from FastAPI OpenAPI (never edit by hand)
```

## Rules for Claude Code
1. One bounded task at a time: state input, output, edge cases, acceptance test.
2. Inspect the repo and propose a plan before schema changes or large refactors.
3. Run tests after each task. Compiling is not "done".
4. Never commit customer files, secrets or credentials. `data/` stays local.
5. Pin dependencies; check licences allow commercial use (avoid GPL in shipped code; LibreDWG is GPL → use only as an external CLI converter, never linked/bundled).
6. Mock/sample data must be clearly labelled; never present mock output as real CAD/GIS processing.
7. Engineering rules live in config (`backend/app/rules/*.yaml`), each with `source`, `approved_by`, `status: TBC|approved`.
8. Frontend: Angular style — standalone components, typed reactive forms, services + RxJS, no `any`.

# Plan & Scope

Source: *OPTICORE Software Team Development Plan* (ERA internal PDF) — original estimate 1,044 person-hours / 16 weeks for a full team.
Reality: one developer (Angular) + Claude Code. So we deliver in tiers.

| Tier | Target duration (full-time) | Outcome |
|---|---|---|
| **Prototype** (current) | ~2 weeks (8–10 working days) | End-to-end workflow on the reference project, simplified rules |
| Pilot | +1–1.5 months | Approved rules, route editing, revisions, robust error handling |
| MVP (as in plan) | ~3–4 months total | Full plan scope: tests, security, DWG decision, verified exports |

Commit externally only to the Prototype. Re-estimate after it.

## Prototype scope
| Area | Included | Deferred |
|---|---|---|
| Projects & files | CRUD, upload, status | Auth/roles |
| KML/KMZ | Import boundary + placemarks, show on map | — |
| CAD | DXF import (DWG converted first), buildings + IDs extraction | Direct DWG, DWG export |
| Survey Excel | Template download, upload, row validation, link to buildings by ID | Template versioning |
| Validation | CAD ↔ Excel ↔ IDs consistency report (replaces manual ArcGIS step) | — |
| Design engine | Street graph, service areas, Hub & box placement, shortest routes (networkx) — **provisional rules** | Route-change proposals + approval workflow |
| Lengths & quantities | Route lengths (no wastage), box counts by type | Full BOQ catalog |
| Exports | Excel, KMZ, DXF | As-Built, handover package |

## Day plan
1. Repo, docker-compose, DB schema, projects screen
2. KML upload → map (first demo)
3. DXF import, CRS, building extraction
4. Survey Excel workflow
5–6. Design engine
7. Lengths + quantities
8. Exports
9–10. Test on reference project, fixes, demo

# Design Team Workflow (7 stages)

Source: `OPTICORE_Engineering_Workflow_Template1_Merged.xlsx` (sheets START_HERE, 00_Workflow_Overview).
Reference projects: ZTE, Fiber Home, Decet Life (no single project covers all stages).

| # | Stage | Inputs | Process (today, manual) | Outputs | Software role (prototype) |
|---|---|---|---|---|---|
| 01 | Initial Data & Survey Base Drawing | Original project KMZ (boundary); Google Earth image | Georeference image in AutoCAD with 2 reference points; draw buildings & streets; street names; unique Building IDs | Base DWG, updated KMZ, PDF survey maps | Start from its **outputs** (DWG→DXF, KMZ). Later: auto-draft buildings/streets from OpenStreetMap |
| 02 | Field Survey | Printed PDF maps, survey forms | Collect per building: street, building no., floors, apartments/floor, shops, total users | Filled forms, marked-up maps | Out of scope (offline) |
| 03 | Survey Validation | Forms, maps, base CAD | Fix CAD; ArcGIS Pro → building polygons; extract lat/long to Excel; enter survey data; cross-check CAD/GIS/Excel | Updated CAD, polygon layer, survey Excel | **Automate**: polygonize + ID linking + consistency report |
| 04 | Preliminary & Detailed Design | Survey Excel, CAD, polygons | Service areas, preliminary Hubs; then boxes, cable routes, final Hubs | Preliminary & detailed design DWG | **Core engine** (provisional rules until approved) |
| 05 | BOQ / Lengths | Detailed design DWG | Count boxes by type; cable lengths from routes | Box quantity sheet, cable length sheet | Auto-calculate + Excel export |
| 06 | As-Built | Approved design, execution updates | Update CAD to executed network | As-Built DWG | Later (revisions) |
| 07 | Handover | All final files | Organise & verify package | Handover package | Later |

Workbook refers to sheets **11_Engineering_Rules, 12_Issues_Log, 13_Automation_Assessment** — not received yet.

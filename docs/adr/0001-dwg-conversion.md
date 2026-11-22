# ADR 0001 — DWG → DXF conversion with LibreDWG (external CLI)

- Status: accepted for the prototype
- Date: 2026-11-22

## Context
Design Team drawings arrive as DWG (AutoCAD 2010 / 2018 formats). Our CAD reader (`ezdxf`, MIT) reads DXF only.
We need a DWG → DXF converter that we may use for **commercial** work and later run **on a server**.

## Options reviewed
| Option | Licence | Verdict |
|---|---|---|
| ODA File Converter | Free download, but ODA's FAQ: *"If you are not an ODA member, you can use them for non-commercial applications only."* Commercial / server (SaaS) use needs a paid ODA membership (higher tier for SaaS). | **Rejected** for now (licence). Can be revisited if the company buys an ODA membership. |
| LibreDWG `dwg2dxf` | GPL-3.0-or-later | **Chosen**, used only as a separate program. |
| AutoCAD "Save as DXF" | Needs an AutoCAD licence per user | Fallback: users can always upload DXF directly. |

## Decision
- Use LibreDWG **0.14** (stable release, June 2026) `dwg2dxf`, called as an **external process** (`subprocess`, argument list, no shell, timeout).
- Its path is configured with `OPTICORE_DWG2DXF_PATH`. Without it, DWG uploads fail with a clear message, and DXF still works.
- **Never link, import, or bundle** LibreDWG with our code. If we later ship it inside a Docker image, we must include its licence text and offer its source code. That does not affect the licence of our own code, because LibreDWG runs as a separate program.

## Verification (test region files)
- Stage 01 base drawing (AC1024): converted in 0.3 s. Extraction results are identical to the analysis in docs/03 (855 polygons / 658 / 84 / 113 / 14).
- Stage 03 validated drawing: converted, 921 buildings.
- A large design drawing (AC1032, 8.7 MB): converted with exit code 0 but 70 `ERROR: Invalid ATTRIB…` messages. Block attributes may be incomplete. Check this again before relying on design-drawing attributes.

## Consequences
- LibreDWG is not complete (~90 % DWG coverage), so some drawings may fail or lose data. In that case the user uploads a DXF saved from AutoCAD.
- Installation is a manual admin step (see README).

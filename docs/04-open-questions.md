# Open questions for the Design Team

Status: sent / pending. Update with answers + who confirmed.

## Missing material
- [ ] Sheets 11_Engineering_Rules, 12_Issues_Log, 13_Automation_Assessment
- [x] Stage 01–03 files for the test region received 2026-11-22 (base DWG V1, validated DWG V3, final survey Excel)
- [ ] Stage 04–07 files (design DWG, BOQ / cable-length sheets, as-built, handover) for the same project
- [ ] Quantity/length sheet that belongs to the `Zone e` design drawing (to check how the `…-60m-…` lengths are computed)
- [ ] Which project is the primary test case for Stages 03–05 (Fiber Home / Decet Life)?

## Engineering rules (Stage 04) — blocking for the design engine
- [ ] How are service areas divided (users, streets, distance…)?
- [ ] Network box types and capacity (users/ports) of each
- [ ] Hub selection criteria; max users/boxes per Hub
- [ ] Max distances (Hub→box, box→building)
- [ ] Splitter ratios; cable types/sizes and sizing rule
- [ ] Routing only along streets?

## Lengths & quantities (Stage 05)
- [ ] Cable length = route geometry only, or slack added? Rule?
- [ ] BOQ items beyond boxes and cables (splitters, closures, ducts, poles…)?

## CAD / files
- [ ] Meaning of `baldimg` hatch (red area) — excluded from design?
- [ ] Meaning of layers `500`, `2500`, `1-500`
- [ ] Street names use `xarb.shx` (non-Unicode): can they switch to a Unicode TrueType font, or share the font file?
- [ ] KMZ dated 7-10 vs DWG 11-10 — which is approved?
- [ ] Does the original KMZ ever contain more than the boundary (existing infrastructure)?
- [ ] Do MSAN locations (e.g. 80 & 13) affect Hub placement?
- [ ] Is the survey Excel template (v1.1, sheet `Survey`, 32 columns) standard across projects and survey companies?
- [ ] Building ID: 'ERA' is the survey company (column `Company`), final IDs are `12` / `12-2`. Same rule for other companies?
- [ ] Are the CAD layer names (`Building`, `Serial HomeNEW`, …) a fixed standard or different per drafter?
- [ ] Buildings crossing / outside the project boundary (test region: 56 crossing, 8 outside, with IDs): are they served?

## Survey (Stage 02–03)
- [ ] Meaning and use of `Void / Core`
- [ ] `HP Count / Not Count` and `TE Comment = Delete`: are these buildings excluded from the design?
- [ ] `Total Users` vs `QTY of Home Pass`: which one drives the design?
- [ ] `Building Entrance Length (m)` (mostly 5 m): is it added to the drop cable length?

## Design drawing conventions (seen in `Zone e`, another region)
- [ ] Box types `11S1..3`, `9ES1..4`, `10S4`: what do 9/10/11 (ports?) and S/ES 1–4 mean? Capacity of each?
- [ ] Layers `01-L1` … `06-L6`: what is L1–L6 (cable leg / Hub port / level)?
- [ ] Label `<hub>-L<n>-<type>-B<n>-<len>m-<pos>`: is `<len>` the route length, or route + slack?
- [ ] `Hub Box 8 port`: 8 ports, but up to 6 L-layers — rule?

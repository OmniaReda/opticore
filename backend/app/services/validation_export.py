"""Validation report → Excel (.xlsx), so the Design Team can work through it like their own sheets."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas import IssueSeverity, ValidationReport

_FILL = {
    IssueSeverity.error: PatternFill("solid", fgColor="F8D7DA"),
    IssueSeverity.warning: PatternFill("solid", fgColor="FFF3CD"),
    IssueSeverity.info: PatternFill("solid", fgColor="E2E3E5"),
}


def _table(ws: Worksheet, header: list[str], rows: list[list[object]], widths: list[int]) -> None:
    ws.append(header)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for i, width in enumerate(widths):
        ws.column_dimensions[chr(ord("A") + i)].width = width
    ws.freeze_panes = "A2"


def to_xlsx(project_name: str, report: ValidationReport) -> bytes:
    wb = Workbook()
    summary = wb.active
    assert summary is not None
    summary.title = "Summary"
    summary.append([f"Validation report — {project_name}"])
    summary["A1"].font = Font(bold=True, size=14)
    if report.provisional:
        summary.append(["Provisional rules (status TBC) — thresholds not confirmed by the Design Team"])
    summary.append([f"GPS distance limit: {report.gps_max_distance_m:.0f} m"])
    summary.append([])
    start = summary.max_row + 1
    _table(
        summary,
        ["Severity", "Check", "Issues"],
        [[r.severity.value, r.title, r.count] for r in report.rules],
        [12, 60, 10],
    )
    summary.freeze_panes = None
    for row, rule in enumerate(report.rules, start=start + 1):
        summary.cell(row=row, column=1).fill = _FILL[rule.severity]

    issues = wb.create_sheet("Issues")
    titles = {r.rule: r.title for r in report.rules}
    _table(
        issues,
        ["Severity", "Check", "Building ID", "Survey row", "Details", "Longitude", "Latitude"],
        [
            [
                i.severity.value,
                titles.get(i.rule, i.rule.value),
                i.code,
                i.row_number,
                i.message,
                *(i.geometry.coordinates[:2] if i.geometry and i.geometry.type == "Point" else [None, None]),
            ]
            for i in report.issues
        ],
        [10, 45, 12, 11, 70, 13, 13],
    )
    for row, issue in enumerate(report.issues, start=2):
        issues.cell(row=row, column=1).fill = _FILL[issue.severity]

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

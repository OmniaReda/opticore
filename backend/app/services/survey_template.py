"""Empty survey Excel with exactly the columns the importer reads (app/rules/survey_columns.yaml)."""

import io

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app import rules

_REQUIRED_FILL = PatternFill("solid", fgColor="FFF3CD")

_HELP: dict[str, str] = {
    "code": "Building ID as written on the drawing, e.g. 12 or 12-2 (without the survey company prefix).",
    "latitude": "Decimal degrees (WGS 84), e.g. 30.115158",
    "longitude": "Decimal degrees (WGS 84), e.g. 31.305530",
    "visit_date": "Date of the visit",
    "total_users": "Floors × Users per Floor + GF Users",
}


def to_xlsx() -> bytes:
    cfg = rules.survey_columns()
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = cfg.sheet
    for _ in range(cfg.header_row - 1):
        ws.append([])
    ws.append(list(cfg.columns.values()))
    for i, field in enumerate(cfg.columns, start=1):
        cell = ws.cell(row=cfg.header_row, column=i)
        cell.font = Font(bold=True)
        if field in cfg.required:
            cell.fill = _REQUIRED_FILL
            cell.comment = Comment("Required", "OPTICORE")
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(str(cell.value)) + 2)
    ws.freeze_panes = ws.cell(row=cfg.header_row + 1, column=1).coordinate

    info = wb.create_sheet("Instructions")
    info.append(["OPTICORE survey template"])
    info["A1"].font = Font(bold=True, size=14)
    info.append([f"Fill sheet '{cfg.sheet}', one row per building, from row {cfg.header_row + 1}."])
    info.append(["Columns are matched by their header text: keep the headers, the order may change."])
    info.append(["Yellow headers are required. Do not add personal data (names of surveyors or representatives)."])
    if cfg.provisional:
        info.append(["Column list is provisional (status TBC)."])
    info.append([])
    info.append(["Column", "Required", "Notes"])
    for cell in info[info.max_row]:
        cell.font = Font(bold=True)
    for field, title in cfg.columns.items():
        info.append([title, "yes" if field in cfg.required else "", _HELP.get(field, "")])
    info.column_dimensions["A"].width = 45
    info.column_dimensions["B"].width = 10
    info.column_dimensions["C"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

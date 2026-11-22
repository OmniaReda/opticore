"""SAMPLE survey Excel files for tests — synthetic, built with openpyxl, not customer data.

Building IDs match tests/cad_samples.drawing() (1, 2, 3, 3-2, 5, 6, 9) so linking can be tested:
in the drawing → 1, 3, 3-2, 5, 6 · survey only → 7 · drawing only → 2, 9.
"""

import io
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from pyproj import Transformer

from app import rules
from tests.kml_samples import _X0, _Y0

COLUMNS = rules.survey_columns().columns
PERSONAL_NAME = "SAMPLE PERSON NAME"

_to_wgs = Transformer.from_crs(32636, 4326, always_xy=True).transform
LON, LAT = _to_wgs(_X0 + 20, _Y0 + 15)  # inside building 1 of the sample drawing
LON_B2, LAT_B2 = _to_wgs(_X0 + 50, _Y0 + 15)  # inside building 2
LON_B6, LAT_B6 = _to_wgs(_X0 + 260, _Y0 + 55)  # inside building 6


def _header() -> list[str]:
    # Different order than the template, odd spacing / case, plus columns we must NOT import.
    titles = [COLUMNS[f] for f in reversed(list(COLUMNS))]
    titles[0] = "  " + titles[0].upper() + "  "
    return ["Surveyor Name", *titles, "TE Rep Name"]


def _row(header: list[str], **values: Any) -> list[Any]:
    titles: dict[str, str] = {str(k): v for k, v in COLUMNS.items()}
    by_title = {" ".join(titles[f].split()).casefold(): v for f, v in values.items()}
    row = [by_title.get(" ".join(h.split()).casefold()) for h in header]
    row[0] = row[-1] = PERSONAL_NAME
    return row


def workbook_bytes(sheet: str = "Survey", drop_column: str | None = None, with_problems: bool = False) -> bytes:
    """with_problems adds rows for the validation checks: wrong Total Users formula, Home Pass ≠ Total Users,
    a row marked Delete / Not Count (all on ID 2), and a second row for ID 6."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet
    header = [h for h in _header() if drop_column is None or h.strip().casefold() != drop_column.casefold()]
    ws.append(header)
    rows = [
        _row(
            header,
            code=1,
            visit_date=datetime(2026, 1, 5),
            street_name="  شارع   تجريبي ",
            latitude=LAT,
            longitude=LON,
            floors=4,
            users_per_floor=2,
            gf_users=2,
            total_users=10,
            hp_count="Count",
        ),
        _row(header, code="3-2", latitude=LAT, longitude=LON, floors="5", users_per_floor="1", total_users="5"),
        _row(header, code=3.0, latitude=LAT, longitude=LON, total_users=3, building_number=171),
        _row(header, code="7", total_users=2),  # no GPS
        _row(header, code="5", latitude=300, longitude=LON),  # invalid latitude
        _row(header, code="6", latitude=LAT, longitude=LON, floors="many"),  # unreadable number
        _row(header, street_name="row without ID", latitude=LAT, longitude=LON),
        [None] * len(header),  # blank line
    ]
    if with_problems:
        rows += [
            _row(
                header,
                code="2",
                latitude=LAT_B2,
                longitude=LON_B2,
                floors=3,
                users_per_floor=2,
                gf_users=1,
                total_users=9,
                qty_home_pass=8,
                te_comment="Delete",
                hp_count="Not Count",
            ),
            _row(header, code="6", latitude=LAT_B6, longitude=LON_B6, total_users=4),
        ]
    for r in rows:
        ws.append(r)
    wb.create_sheet("Daily").append(["other sheets are ignored"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

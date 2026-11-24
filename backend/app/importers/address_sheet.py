"""Read the Streets & numbers Excel back after the field team filled Floors and Total Users.

The file is the one made by the streets export (sheet `Addresses`): one row per OpenStreetMap house number
with its location. Rows are kept when they have Total Users or Floors and a valid location.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from shapely.geometry import Point

from app.importers import FileContentError
from app.importers.survey import UnreadableError, to_float, to_int, to_text

SHEET = "Addresses"
STREET_AR = "Street (Arabic)"
STREET_EN = "Street (English)"
HOUSE_NUMBER = "House number"
LATITUDE = "Latitude"
LONGITUDE = "Longitude"


class AddressSheetError(FileContentError):
    pass


@dataclass
class AddressRow:
    row_number: int
    street_ar: str | None
    street_en: str | None
    house_number: str | None
    floors: int | None
    total_users: int | None
    point: Point


@dataclass
class AddressContent:
    rows: list[AddressRow] = field(default_factory=list)
    empty: int = 0  # no Floors and no Total Users written
    bad_location: int = 0
    unreadable: int = 0  # Floors / Total Users cells that are not whole numbers


def is_address_sheet(path: Path) -> bool:
    """True for a Streets & numbers Excel (has the Addresses sheet and no other survey sheet)."""
    try:
        workbook = load_workbook(path, read_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError):
        return False
    try:
        return SHEET in workbook.sheetnames
    finally:
        workbook.close()


def _norm(value: Any) -> str:
    return " ".join(str(value).split()).casefold() if value is not None else ""


def read(path: Path, floors_title: str, users_title: str) -> AddressContent:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as e:
        raise AddressSheetError(f"Not a readable Excel (.xlsx) file: {e}") from None
    try:
        rows = workbook[SHEET].iter_rows(values_only=True)
        header = next(rows, None) or ()
        index = {_norm(h): i for i, h in enumerate(header) if h is not None}
        wanted = [STREET_AR, STREET_EN, HOUSE_NUMBER, LATITUDE, LONGITUDE, floors_title, users_title]
        missing = [t for t in wanted if _norm(t) not in index]
        if missing:
            raise AddressSheetError(f"Sheet '{SHEET}': columns not found: {', '.join(missing)}")
        col = {t: index[_norm(t)] for t in wanted}

        content = AddressContent()
        for number, cells in enumerate(rows, start=2):

            def cell(title: str, cells: tuple[Any, ...] = cells) -> Any:
                value = cells[col[title]] if col[title] < len(cells) else None
                return None if isinstance(value, str) and not value.strip() else value

            counts: list[int | None] = []
            for title in (floors_title, users_title):
                raw = cell(title)
                try:
                    counts.append(None if raw is None else to_int(raw))
                except UnreadableError:
                    counts.append(None)
                    content.unreadable += 1
            floors, users = counts
            if floors is None and users is None:
                content.empty += 1
                continue
            try:
                lat, lon = to_float(cell(LATITUDE)), to_float(cell(LONGITUDE))
            except UnreadableError:
                content.bad_location += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                content.bad_location += 1
                continue
            content.rows.append(
                AddressRow(
                    number,
                    to_text(cell(STREET_AR)) if cell(STREET_AR) is not None else None,
                    to_text(cell(STREET_EN)) if cell(STREET_EN) is not None else None,
                    to_text(cell(HOUSE_NUMBER)) if cell(HOUSE_NUMBER) is not None else None,
                    floors,
                    users,
                    Point(lon, lat),
                )
            )
        return content
    finally:
        workbook.close()

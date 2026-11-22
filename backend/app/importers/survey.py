"""Read the field-survey Excel (.xlsx). Columns are found by header text (app/rules/survey_columns.yaml).

Values are typed leniently (Excel cells often hold numbers as text, IDs as floats); a cell that cannot be
read is left empty and counted, so one bad cell never blocks the whole survey.
"""

from __future__ import annotations

import warnings
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from shapely.geometry import Point

from app.importers import FileContentError
from app.rules import SurveyColumnRules, SurveyField


class SurveyError(FileContentError):
    pass


class _UnreadableError(Exception):
    pass


def _text(value: Any) -> str | None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # IDs / numbers typed as 12.0 → "12"
    if isinstance(value, datetime):
        value = value.date()
    text = " ".join(str(value).split())
    return text or None


def _int(value: Any) -> int:
    if isinstance(value, bool):
        raise _UnreadableError
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    raise _UnreadableError


def _float(value: Any) -> float:
    if isinstance(value, bool):
        raise _UnreadableError
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        raise _UnreadableError from None


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise _UnreadableError from None


_INT_FIELDS = {"floors", "users_per_floor", "gf_users", "total_users", "hp_te_required", "qty_home_pass"}
_FLOAT_FIELDS = {"latitude", "longitude", "entrance_length_m"}


def _converter(name: SurveyField) -> Callable[[Any], Any]:
    if name in _INT_FIELDS:
        return _int
    if name in _FLOAT_FIELDS:
        return _float
    if name == "visit_date":
        return _date
    return _text


@dataclass
class SurveyRow:
    row_number: int  # as shown in Excel
    code: str  # Building ID
    values: dict[SurveyField, Any]  # typed values; None = empty or unreadable
    point: Point | None  # lon/lat (EPSG:4326) when the GPS cells are valid


@dataclass
class SurveyContent:
    rows: list[SurveyRow]
    rows_without_id: int = 0
    unreadable: Counter[SurveyField] = field(default_factory=Counter)
    missing_gps: int = 0
    invalid_gps: int = 0
    unmatched_columns: list[SurveyField] = field(default_factory=list)  # optional columns not in this file


def _normalize(header: Any) -> str:
    return " ".join(str(header).split()).casefold() if header is not None else ""


def _gps(values: dict[SurveyField, Any], content: SurveyContent) -> Point | None:
    lat, lon = values.get("latitude"), values.get("longitude")
    if lat is None and lon is None:
        content.missing_gps += 1
        return None
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        content.invalid_gps += 1
        return None
    return Point(lon, lat)


def read(path: Path, rules: SurveyColumnRules) -> SurveyContent:
    with warnings.catch_warnings():
        # Excel data-validation lists are not needed; openpyxl warns (while reading rows) that it drops them.
        warnings.filterwarnings("ignore", message="Data Validation extension", category=UserWarning)
        return _read(path, rules)


def _read(path: Path, rules: SurveyColumnRules) -> SurveyContent:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as e:
        raise SurveyError(f"Not a readable Excel (.xlsx) file: {e}") from None
    try:
        if rules.sheet not in workbook.sheetnames:
            raise SurveyError(f"Sheet '{rules.sheet}' not found. Sheets in this file: {', '.join(workbook.sheetnames)}")
        rows = workbook[rules.sheet].iter_rows(min_row=rules.header_row, values_only=True)
        header = next(rows, None) or ()
        index = {_normalize(h): i for i, h in enumerate(header) if h is not None}

        columns: dict[SurveyField, int] = {}
        for name, title in rules.columns.items():
            if _normalize(title) in index:
                columns[name] = index[_normalize(title)]
        missing = [rules.columns[f] for f in rules.required if f not in columns]
        if missing:
            found = ", ".join(str(h) for h in header if h is not None)
            raise SurveyError(
                f"Required columns not found: {', '.join(missing)}. Columns in row {rules.header_row}: {found}"
            )

        content = SurveyContent(rows=[], unmatched_columns=[f for f in rules.columns if f not in columns])
        for offset, cells in enumerate(rows, start=1):
            if all(c is None or (isinstance(c, str) and not c.strip()) for c in cells):
                continue  # blank line
            values: dict[SurveyField, Any] = {}
            for name, col in columns.items():
                raw = cells[col] if col < len(cells) else None
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    values[name] = None
                    continue
                try:
                    values[name] = _converter(name)(raw)
                except _UnreadableError:
                    values[name] = None
                    content.unreadable[name] += 1
            code = values.pop("code", None)
            if not code:
                content.rows_without_id += 1
                continue
            content.rows.append(SurveyRow(rules.header_row + offset, str(code), values, _gps(values, content)))
        return content
    finally:
        workbook.close()

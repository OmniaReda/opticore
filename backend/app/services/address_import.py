"""Import the filled Streets & numbers Excel: one AddressPoint per row with Floors or Total Users.

The latest such file replaces the address points of earlier ones. The survey (Building IDs) is not touched.
"""

from geoalchemy2.shape import from_shape
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import geo, rules, storage
from app.importers import address_sheet
from app.models import AddressPoint, Project, ProjectFile


def import_addresses(db: Session, record: ProjectFile) -> str:
    columns = rules.survey_columns().columns
    floors, users = columns["floors"], columns["total_users"]
    content = address_sheet.read(storage.absolute_path(record.stored_path), floors, users)
    if not content.rows:
        raise address_sheet.AddressSheetError(
            f"Sheet '{address_sheet.SHEET}': no row has {floors} or {users} filled in. "
            "Fill them for the buildings you surveyed and upload the file again."
        )
    db.get_one(Project, record.project_id, with_for_update=True)
    db.execute(delete(AddressPoint).where(AddressPoint.project_id == record.project_id))
    db.add_all(
        AddressPoint(
            project_id=record.project_id,
            source_file_id=record.id,
            row_number=r.row_number,
            street_ar=r.street_ar,
            street_en=r.street_en,
            house_number=r.house_number,
            floors=r.floors,
            total_users=r.total_users,
            geometry=from_shape(r.point, srid=geo.STORAGE_SRID),
        )
        for r in content.rows
    )
    total = sum(r.total_users or 0 for r in content.rows)
    parts = [f"Addresses (Streets & numbers): {len(content.rows)} rows with data", f"{total} users"]
    no_users = sum(1 for r in content.rows if r.total_users is None)
    if no_users:
        parts.append(f"{no_users} with Floors but no {users}")
    if content.empty:
        parts.append(f"{content.empty} rows not filled yet")
    if content.bad_location:
        parts.append(f"{content.bad_location} rows without a valid location skipped")
    if content.unreadable:
        parts.append(f"{content.unreadable} cells that are not whole numbers")
    return " · ".join(parts)

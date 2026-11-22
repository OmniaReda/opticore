"""Process an uploaded survey Excel: one SurveyRecord per row.

The most recently imported survey is THE survey of the project: importing a file replaces the rows
that came from any earlier survey file.
"""

from collections import Counter

from geoalchemy2.shape import from_shape
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import geo, rules, storage
from app.importers import survey
from app.models import FileKind, Project, ProjectFile, SurveyRecord

SURVEY_KINDS = {FileKind.survey_xlsx}


def import_survey(db: Session, record: ProjectFile) -> str:
    """Import into the DB session (not committed). Returns the note shown to the user."""
    cfg = rules.survey_columns()
    content = survey.read(storage.absolute_path(record.stored_path), cfg)
    if not content.rows:
        raise survey.SurveyError(f"No survey rows with a Building ID in sheet '{cfg.sheet}'")

    # Lock the project row: two surveys processed at once must not mix their rows.
    db.get_one(Project, record.project_id, with_for_update=True)
    previous = db.scalars(
        select(SurveyRecord.source_file_id).where(SurveyRecord.project_id == record.project_id).distinct()
    ).all()
    db.execute(delete(SurveyRecord).where(SurveyRecord.project_id == record.project_id))
    db.add_all(
        SurveyRecord(
            project_id=record.project_id,
            source_file_id=record.id,
            row_number=row.row_number,
            code=row.code,
            geometry=from_shape(row.point, srid=geo.STORAGE_SRID) if row.point is not None else None,
            **row.values,
        )
        for row in content.rows
    )

    duplicates = sum(1 for n in Counter(r.code for r in content.rows).values() if n > 1)
    parts = [f"Sheet '{cfg.sheet}'", f"{len(content.rows)} rows"]
    if content.rows_without_id:
        parts.append(f"{content.rows_without_id} rows without ID skipped")
    if duplicates:
        parts.append(f"{duplicates} IDs used more than once")
    if content.missing_gps or content.invalid_gps:
        parts.append(f"GPS missing on {content.missing_gps} rows, invalid on {content.invalid_gps}")
    if content.unreadable:
        cells = ", ".join(f"{cfg.columns[f]} ({n})" for f, n in content.unreadable.most_common())
        parts.append(f"unreadable cells: {cells}")
    if content.unmatched_columns:
        parts.append(f"columns not in file: {', '.join(cfg.columns[f] for f in content.unmatched_columns)}")
    if any(f != record.id for f in previous):
        parts.append("replaced survey from a previous file")
    return " · ".join(parts)

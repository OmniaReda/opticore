"""Survey of a project: imported rows, linked to the drawing's Building IDs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import rules
from app.models import BuildingLabel, Project, SurveyRecord
from app.schemas import SurveyLayer, SurveyRecordRead, SurveySummary
from app.services.buildings import natural_key


def survey_layer(db: Session, project: Project) -> SurveyLayer:
    rows = db.scalars(select(SurveyRecord).where(SurveyRecord.project_id == project.id)).all()
    drawing_ids = set(db.scalars(select(BuildingLabel.code).where(BuildingLabel.project_id == project.id)))
    survey_ids = {r.code for r in rows}

    records = sorted(
        (SurveyRecordRead.model_validate(r).model_copy(update={"in_drawing": r.code in drawing_ids}) for r in rows),
        key=lambda r: (natural_key(r.code), r.row_number),
    )
    not_in_drawing = sorted(survey_ids - drawing_ids, key=natural_key) if drawing_ids else []
    without_survey = sorted(drawing_ids - survey_ids, key=natural_key) if rows else []

    summary = SurveySummary(
        rows=len(records),
        in_drawing=sum(1 for r in records if r.in_drawing),
        not_in_drawing=sum(1 for r in records if drawing_ids and not r.in_drawing),
        drawing_ids_without_survey=len(without_survey),
        missing_gps=sum(1 for r in rows if r.geometry is None),
        total_users=sum(r.total_users or 0 for r in rows),
    )
    return SurveyLayer(
        source_file_id=rows[0].source_file_id if rows else None,
        provisional=rules.survey_columns().provisional,
        has_drawing=bool(drawing_ids),
        summary=summary,
        records=records,
        not_in_drawing=not_in_drawing,
        drawing_ids_without_survey=without_survey,
    )

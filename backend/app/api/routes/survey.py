from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, ProjectDep
from app.schemas import SurveyLayer
from app.services import survey
from app.services import survey_template as survey_template_service

router = APIRouter(prefix="/projects/{project_id}/survey", tags=["survey"])


@router.get("")
def get_survey(project: ProjectDep, db: DbSession) -> SurveyLayer:
    """Survey rows of the latest imported survey Excel, linked to the drawing's Building IDs."""
    return survey.survey_layer(db, project)


template_router = APIRouter(prefix="/survey", tags=["survey"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@template_router.get("/template", response_class=Response, responses={200: {"content": {XLSX: {}}}})
def survey_template() -> Response:
    """Empty survey Excel with the columns OPTICORE reads (fill it, then upload it to a project)."""
    return Response(
        survey_template_service.to_xlsx(),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="survey-template.xlsx"'},
    )

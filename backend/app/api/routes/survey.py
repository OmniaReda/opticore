from fastapi import APIRouter

from app.api.deps import DbSession, ProjectDep
from app.schemas import SurveyLayer
from app.services import survey

router = APIRouter(prefix="/projects/{project_id}/survey", tags=["survey"])


@router.get("")
def get_survey(project: ProjectDep, db: DbSession) -> SurveyLayer:
    """Survey rows of the latest imported survey Excel, linked to the drawing's Building IDs."""
    return survey.survey_layer(db, project)

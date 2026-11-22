from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, ProjectDep
from app.schemas import ValidationReport
from app.services import validation, validation_export

router = APIRouter(prefix="/projects/{project_id}/validation", tags=["validation"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("")
def get_validation(project: ProjectDep, db: DbSession) -> ValidationReport:
    """Consistency report between the drawing's Building IDs and the survey Excel (Stage 03)."""
    return validation.report(db, project)


@router.get("/export", response_class=Response, responses={200: {"content": {XLSX: {}}}})
def export_validation(project: ProjectDep, db: DbSession) -> Response:
    """The same report as an Excel file (one sheet with the summary, one with every issue)."""
    content = validation_export.to_xlsx(project.name, validation.report(db, project))
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="validation-report.xlsx"'},
    )

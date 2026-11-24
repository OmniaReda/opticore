from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, ProjectDep
from app.schemas import BoxDesign, BoxDesignDefaults, BoxDesignRequest
from app.services import box_design

router = APIRouter(tags=["network boxes"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_NEEDS: dict[int | str, dict[str, Any]] = {
    409: {"description": "No drawing or no survey users yet"},
    422: {"description": "Unusable values"},
}


@router.get("/network-boxes/defaults")
def get_box_defaults() -> BoxDesignDefaults:
    """Box types, drop limit and spare share from backend/app/rules/network_boxes.yaml (empty until confirmed)."""
    return box_design.defaults()


@router.post("/projects/{project_id}/network-boxes/design", responses=_NEEDS)
def design_boxes(project: ProjectDep, db: DbSession, body: BoxDesignRequest) -> BoxDesign:
    """Place Network Boxes on the drawing's buildings, sized by the survey's Total Users (provisional)."""
    return box_design.design(db, project, body)


@router.post(
    "/projects/{project_id}/network-boxes/design/xlsx",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}}, **_NEEDS},
)
def export_box_design(project: ProjectDep, db: DbSession, body: BoxDesignRequest) -> Response:
    """The same design as Excel: boxes, the box of each building, buildings not served, settings."""
    content = box_design.to_xlsx(project, box_design.design(db, project, body))
    headers = {"Content-Disposition": 'attachment; filename="network-boxes.xlsx"'}
    return Response(content, media_type=XLSX, headers=headers)

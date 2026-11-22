from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "unreachable"]


@router.get("/health", responses={503: {"model": Health, "description": "Database not reachable"}})
def health(db: DbSession, response: Response) -> Health:
    """Liveness + database check."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(status="error", database="unreachable")
    return Health(status="ok", database="ok")

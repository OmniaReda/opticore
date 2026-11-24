from fastapi import APIRouter

from app.api.deps import DbSession, ProjectDep
from app.schemas import AddressLayer
from app.services import addresses

router = APIRouter(prefix="/projects/{project_id}/addresses", tags=["addresses"])


@router.get("")
def get_addresses(project: ProjectDep, db: DbSession) -> AddressLayer:
    """House numbers with Floors / Total Users from the filled Streets & numbers Excel (EPSG:4326)."""
    return addresses.address_layer(db, project)

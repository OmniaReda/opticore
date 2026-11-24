"""Address points of a project (the filled Streets & numbers Excel)."""

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo
from app.models import AddressPoint, Project
from app.schemas import AddressLayer, AddressPointRead, AddressSummary


def points(db: Session, project: Project) -> list[AddressPoint]:
    query = select(AddressPoint).where(AddressPoint.project_id == project.id).order_by(AddressPoint.row_number)
    return list(db.scalars(query))


def label(p: AddressPoint) -> str:
    """'12 شارع …' — how an address is named in the box design (there is no Building ID)."""
    street = p.street_ar or p.street_en
    return " ".join(part for part in (p.house_number, street) if part) or f"row {p.row_number}"


def address_layer(db: Session, project: Project) -> AddressLayer:
    rows = points(db, project)
    return AddressLayer(
        source_file_id=rows[0].source_file_id if rows else None,
        summary=AddressSummary(
            rows=len(rows),
            total_users=sum(r.total_users or 0 for r in rows),
            without_users=sum(1 for r in rows if r.total_users is None),
        ),
        points=[
            AddressPointRead(
                id=r.id,
                row_number=r.row_number,
                street_ar=r.street_ar,
                street_en=r.street_en,
                house_number=r.house_number,
                floors=r.floors,
                total_users=r.total_users,
                geometry=geo.to_geojson(to_shape(r.geometry)),
            )
            for r in rows
        ],
    )

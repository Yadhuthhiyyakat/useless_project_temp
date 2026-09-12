"""Death records API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.database.models import Death
from app.schemas.death import DeathListResponse, DeathResponse
from app.services.cause_service import DeathCause
from app.services.lifespan_service import humanize_lifespan
from sqlalchemy import func, select

router = APIRouter()


def _death_to_response(death: Death) -> DeathResponse:
    try:
        cause_label = DeathCause(death.cause).label
    except ValueError:
        cause_label = death.cause
    return DeathResponse(
        id=death.id,
        file_id=death.file_id,
        filename=death.filename,
        original_path=death.original_path,
        extension=death.extension,
        size_bytes=death.size_bytes,
        born_at=death.born_at,
        last_modified_at=death.last_modified_at,
        deleted_at=death.deleted_at,
        lifespan_seconds=death.lifespan_seconds,
        lifespan_label=humanize_lifespan(death.lifespan_seconds),
        cause=death.cause,
        cause_label=cause_label,
        epitaph=death.epitaph,
        cemetery_x=death.cemetery_x,
        cemetery_y=death.cemetery_y,
        created_at=death.created_at,
    )


@router.get(
    "/deaths",
    response_model=DeathListResponse,
    summary="List death records",
    description="Paginated death records, newest first. Supports filtering by cause, extension and free-text search.",
)
def list_deaths(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    cause: str | None = Query(None, description="Filter by cause"),
    extension: str | None = Query(None, description="Filter by extension, e.g. .txt"),
    q: str | None = Query(None, description="Search in filename or original_path"),
) -> DeathListResponse:
    database = request.app.state.database
    with database.session() as session:
        base = select(Death)
        count_base = select(func.count()).select_from(Death)

        filters = []
        if cause is not None:
            filters.append(Death.cause == cause)
        if extension is not None:
            filters.append(Death.extension == extension)
        if q is not None:
            like = f"%{q}%"
            filters.append((Death.filename.ilike(like)) | (Death.original_path.ilike(like)))

        if filters:
            base = base.where(*filters)
            count_base = count_base.where(*filters)

        total = int(session.scalar(count_base) or 0)
        stmt = base.order_by(Death.deleted_at.desc(), Death.id.desc()).limit(limit).offset(offset)
        deaths = list(session.scalars(stmt))

    items = [_death_to_response(d) for d in deaths]
    return DeathListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/deaths/{death_id}",
    response_model=DeathResponse,
    summary="Get a death record",
    description="Fetch a single death record by id.",
    responses={404: {"description": "Death not found"}},
)
def get_death(request: Request, death_id: int) -> DeathResponse:
    database = request.app.state.database
    with database.session() as session:
        death = session.get(Death, death_id)
        if death is None:
            raise HTTPException(status_code=404, detail="Death not found")
        # detach before session closes — response is built from the loaded object
        return _death_to_response(death)

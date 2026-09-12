"""Statistics and timeline API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.database.models import Death
from app.schemas.statistics import StatisticsResponse, TimelineEvent, TimelineResponse
from app.services.cause_service import DeathCause
from app.services.lifespan_service import humanize_lifespan
from app.services.statistics_service import StatisticsService
from sqlalchemy import func, select

router = APIRouter()


@router.get(
    "/statistics",
    response_model=StatisticsResponse,
    summary="Cemetery statistics",
    description="Aggregate counts, average lifespan, and breakdowns by cause/extension.",
)
def statistics(request: Request) -> StatisticsResponse:
    database = request.app.state.database
    service = StatisticsService(database)
    return service.summary()


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Cemetery timeline",
    description="Chronological death events, newest first, with pagination and optional date range.",
)
def timeline(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
) -> TimelineResponse:
    database = request.app.state.database
    with database.session() as session:
        base = select(Death)
        count_base = select(func.count()).select_from(Death)

        if from_ is not None:
            base = base.where(Death.deleted_at >= from_)
            count_base = count_base.where(Death.deleted_at >= from_)
        if to is not None:
            base = base.where(Death.deleted_at <= to)
            count_base = count_base.where(Death.deleted_at <= to)

        total = int(session.scalar(count_base) or 0)
        stmt = base.order_by(Death.deleted_at.desc(), Death.id.desc()).limit(limit).offset(offset)
        deaths = list(session.scalars(stmt))

    events = []
    for d in deaths:
        try:
            cause_label = DeathCause(d.cause).label
        except ValueError:
            cause_label = d.cause
        events.append(
            TimelineEvent(
                id=d.id,
                file_id=d.file_id,
                filename=d.filename,
                extension=d.extension,
                deleted_at=d.deleted_at,
                cause=d.cause,
                cause_label=cause_label,
                lifespan_label=humanize_lifespan(d.lifespan_seconds),
                cemetery_x=d.cemetery_x,
                cemetery_y=d.cemetery_y,
            )
        )
    return TimelineResponse(events=events, total=total, limit=limit, offset=offset)
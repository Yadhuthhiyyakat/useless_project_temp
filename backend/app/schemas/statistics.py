"""Pydantic schemas for statistics and timeline endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_deaths: int
    total_lifespan_seconds: int
    average_lifespan_seconds: float
    by_cause: dict[str, int]
    by_extension: dict[str, int]
    oldest_death: datetime | None
    newest_death: datetime | None


class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    filename: str
    extension: str
    deleted_at: datetime
    cause: str
    cause_label: str
    lifespan_label: str
    cemetery_x: float
    cemetery_y: float


class TimelineResponse(BaseModel):
    events: list[TimelineEvent]
    total: int
    limit: int
    offset: int
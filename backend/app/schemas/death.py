"""Pydantic schemas for death records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeathResponse(BaseModel):
    """Single death record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    filename: str
    original_path: str
    extension: str
    size_bytes: int
    born_at: datetime
    last_modified_at: datetime | None
    deleted_at: datetime
    lifespan_seconds: int
    lifespan_label: str
    cause: str
    cause_label: str
    epitaph: str | None
    cemetery_x: float
    cemetery_y: float
    created_at: datetime


class DeathListResponse(BaseModel):
    """Paginated list of death records."""

    items: list[DeathResponse]
    total: int
    limit: int
    offset: int

"""Pydantic schemas for search, watcher status, and settings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    filename: str
    original_path: str
    extension: str
    deleted_at: datetime
    cause: str
    cause_label: str
    lifespan_label: str
    cemetery_x: float
    cemetery_y: float


class SearchResponse(BaseModel):
    items: list[SearchResult]
    total: int
    limit: int
    offset: int
    query: str


class WatcherStatusResponse(BaseModel):
    running: bool
    watched_directories: list[str]


class SettingsResponse(BaseModel):
    watched_directories: list[str]
    ignored_directories: list[str]
    ai_epitaphs_enabled: bool


class SettingsUpdate(BaseModel):
    watched_directories: list[str] | None = None
    ignored_directories: list[str] | None = None
    ai_epitaphs_enabled: bool | None = None
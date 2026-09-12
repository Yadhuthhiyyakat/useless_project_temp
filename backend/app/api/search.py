"""Search, watcher status, and settings API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.database.models import Death
from app.schemas.search import (
    SearchResponse,
    SearchResult,
    SettingsResponse,
    SettingsUpdate,
    WatcherStatusResponse,
)
from app.services.cause_service import DeathCause
from app.services.lifespan_service import humanize_lifespan
from sqlalchemy import func, select

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search death records",
    description="Full-text-ish search across filename and original_path with pagination.",
)
def search_deaths(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SearchResponse:
    database = request.app.state.database
    with database.session() as session:
        like = f"%{q}%"
        base = select(Death).where(
            (Death.filename.ilike(like)) | (Death.original_path.ilike(like))
        )
        total = int(
            session.scalar(
                select(func.count()).select_from(Death).where(
                    (Death.filename.ilike(like)) | (Death.original_path.ilike(like))
                )
            )
            or 0
        )
        stmt = base.order_by(Death.deleted_at.desc(), Death.id.desc()).limit(limit).offset(offset)
        deaths = list(session.scalars(stmt))

    items = []
    for d in deaths:
        try:
            cause_label = DeathCause(d.cause).label
        except ValueError:
            cause_label = d.cause
        items.append(
            SearchResult(
                id=d.id,
                file_id=d.file_id,
                filename=d.filename,
                original_path=d.original_path,
                extension=d.extension,
                deleted_at=d.deleted_at,
                cause=d.cause,
                cause_label=cause_label,
                lifespan_label=humanize_lifespan(d.lifespan_seconds),
                cemetery_x=d.cemetery_x,
                cemetery_y=d.cemetery_y,
            )
        )
    return SearchResponse(items=items, total=total, limit=limit, offset=offset, query=q)


@router.get(
    "/watcher/status",
    response_model=WatcherStatusResponse,
    summary="Watcher status",
    description="Current filesystem watcher state.",
)
def watcher_status(request: Request) -> WatcherStatusResponse:
    watcher = request.app.state.watcher
    return WatcherStatusResponse(
        running=watcher.running, watched_directories=watcher.watched_directories
    )


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get current settings",
    description="Returns watched directories, ignored directories, and AI epitaph toggle.",
)
def get_settings(request: Request) -> SettingsResponse:
    config = request.app.state.config
    return SettingsResponse(
        watched_directories=config.watched_directories,
        ignored_directories=config.ignored_directories,
        ai_epitaphs_enabled=config.ai_epitaphs_enabled,
    )


@router.patch(
    "/settings",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Persistently updates watched/ignored directories and AI epitaph toggle.",
)
def update_settings(request: Request, payload: SettingsUpdate) -> SettingsResponse:
    config = request.app.state.config
    watcher = request.app.state.watcher

    # Persist to database
    from app.database.repositories import (
        SETTING_AI_EPITAPHS_ENABLED,
        SETTING_IGNORED_DIRECTORIES,
        SETTING_WATCHED_DIRECTORIES,
        SettingRepository,
    )

    with request.app.state.database.session() as session:
        repo = SettingRepository(session)
        if payload.watched_directories is not None:
            repo.set(SETTING_WATCHED_DIRECTORIES, payload.watched_directories)
            config.watched_directories = payload.watched_directories
            # Reconfigure watcher
            for d in list(watcher.watched_directories):
                if d not in payload.watched_directories:
                    watcher.remove_directory(d)
            for d in payload.watched_directories:
                if d not in watcher.watched_directories:
                    watcher.add_directory(d)
        if payload.ignored_directories is not None:
            repo.set(SETTING_IGNORED_DIRECTORIES, payload.ignored_directories)
            config.ignored_directories = payload.ignored_directories
        if payload.ai_epitaphs_enabled is not None:
            repo.set(SETTING_AI_EPITAPHS_ENABLED, payload.ai_epitaphs_enabled)
            config.ai_epitaphs_enabled = payload.ai_epitaphs_enabled

    return SettingsResponse(
        watched_directories=config.watched_directories,
        ignored_directories=config.ignored_directories,
        ai_epitaphs_enabled=config.ai_epitaphs_enabled,
    )
"""Search, watcher status, and settings API."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from app.database.models import Death
from app.logging_config import get_logger
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

logger = get_logger(__name__)

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
    database = getattr(request.app.state, "database", None)

    from app.database.repositories import (
        SETTING_AI_EPITAPHS_ENABLED,
        SETTING_IGNORED_DIRECTORIES,
        SETTING_WATCHED_DIRECTORIES,
        SettingRepository,
    )

    watched = config.watched_directories
    ignored = config.ignored_directories
    ai_epitaphs = config.ai_epitaphs_enabled

    if database is not None:
        try:
            with database.session() as session:
                repo = SettingRepository(session)
                db_watched = repo.get(SETTING_WATCHED_DIRECTORIES)
                db_ignored = repo.get(SETTING_IGNORED_DIRECTORIES)
                db_ai = repo.get(SETTING_AI_EPITAPHS_ENABLED)
                if db_watched is not None:
                    watched = db_watched
                if db_ignored is not None:
                    ignored = db_ignored
                if db_ai is not None:
                    ai_epitaphs = db_ai
        except Exception as exc:
            logger.warning("Could not read settings from database: %s", exc)

    return SettingsResponse(
        watched_directories=watched,
        ignored_directories=ignored,
        ai_epitaphs_enabled=ai_epitaphs,
    )


@router.patch(
    "/settings",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Persistently updates watched/ignored directories and AI epitaph toggle.",
)
def update_settings(
    request: Request,
    payload: SettingsUpdate,
    background_tasks: BackgroundTasks,
) -> SettingsResponse:
    config = request.app.state.config
    watcher = getattr(request.app.state, "watcher", None)
    processor = getattr(request.app.state, "processor", None)
    database = request.app.state.database

    from app.database.repositories import (
        SETTING_AI_EPITAPHS_ENABLED,
        SETTING_IGNORED_DIRECTORIES,
        SETTING_WATCHED_DIRECTORIES,
        SettingRepository,
    )
    from app.services.scan_service import ScanService

    clean_dirs: list[str] | None = None
    if payload.watched_directories is not None:
        clean_dirs = []
        for d in payload.watched_directories:
            raw_d = str(d).strip()
            if not raw_d:
                continue
            abs_path = os.path.abspath(raw_d)
            if not os.path.exists(abs_path):
                try:
                    os.makedirs(abs_path, exist_ok=True)
                except OSError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Directory '{raw_d}' could not be created: {exc}",
                    )
            elif not os.path.isdir(abs_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Path '{raw_d}' exists but is not a directory",
                )
            clean_dirs.append(abs_path)

    clean_ignored: list[str] | None = None
    if payload.ignored_directories is not None:
        clean_ignored = [
            os.path.abspath(d.strip()) for d in payload.ignored_directories if str(d).strip()
        ]

    with database.session() as session:
        repo = SettingRepository(session)
        if clean_dirs is not None:
            repo.set(SETTING_WATCHED_DIRECTORIES, clean_dirs)
            config.watched_directories = clean_dirs
        if clean_ignored is not None:
            repo.set(SETTING_IGNORED_DIRECTORIES, clean_ignored)
            config.ignored_directories = clean_ignored
        if payload.ai_epitaphs_enabled is not None:
            repo.set(SETTING_AI_EPITAPHS_ENABLED, payload.ai_epitaphs_enabled)
            config.ai_epitaphs_enabled = payload.ai_epitaphs_enabled

    # After DB commit: reconfigure processor and watcher
    if clean_dirs is not None:
        if processor is not None and hasattr(processor, "update_directories"):
            processor.update_directories(watched_directories=clean_dirs)

        existing_watched = set(watcher.watched_directories) if watcher is not None else set()
        new_dirs = [d for d in clean_dirs if d not in existing_watched]

        if watcher is not None:
            for d in list(watcher.watched_directories):
                if d not in clean_dirs:
                    watcher.remove_directory(d)
            for d in clean_dirs:
                if d not in watcher.watched_directories:
                    try:
                        watcher.add_directory(d)
                    except Exception as exc:
                        logger.warning("Could not add directory to watcher %s: %s", d, exc)

        scan_service = ScanService(database)
        dirs_to_scan = new_dirs + [d for d in clean_dirs if d not in new_dirs]
        for d in dirs_to_scan:
            background_tasks.add_task(
                scan_service.scan_directory,
                d,
                ignored_directories=config.ignored_directories,
            )

    if clean_ignored is not None and processor is not None and hasattr(processor, "update_directories"):
        processor.update_directories(ignored_directories=clean_ignored)

    return SettingsResponse(
        watched_directories=config.watched_directories,
        ignored_directories=config.ignored_directories,
        ai_epitaphs_enabled=config.ai_epitaphs_enabled,
    )
"""FastAPI application factory for the Digital Cemetery backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.deaths import router as deaths_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.statistics import router as statistics_router
from app.config import Config, default_config
from app.database.database import Database
from app.logging_config import get_logger, setup_logging
from app.watcher.filesystem import FileEventHandler, WatcherError, WatcherService
from app.watcher.processor import EventProcessor
import time
import uuid

logger = get_logger(__name__)

APP_TITLE = "Digital Cemetery"
APP_DESCRIPTION = (
    "Local privacy-focused filesystem monitoring application that records "
    "permanent digital death records for deleted files."
)
APP_VERSION = "0.1.0"


def create_app(config: Config | None = None) -> FastAPI:
    """Build a configured FastAPI instance.

    Args:
        config: Application configuration. Defaults to ``default_config``.
    """
    config = config or default_config
    setup_logging(config)

    database = Database(config)

    processor = EventProcessor(
        database,
        ignored_directories=config.ignored_directories,
        watched_directories=config.watched_directories,
    )
    handler = FileEventHandler(processor)
    watcher = WatcherService(handler)
    for directory in config.watched_directories:
        try:
            watcher.add_directory(directory)
        except WatcherError as exc:
            logger.warning("Skipping configured directory: %s", exc)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("Digital Cemetery backend starting (version %s)", APP_VERSION)
        database.init()

        from app.database.repositories import (
            SETTING_AI_EPITAPHS_ENABLED,
            SETTING_IGNORED_DIRECTORIES,
            SETTING_WATCHED_DIRECTORIES,
            SettingRepository,
        )

        with database.session() as session:
            repo = SettingRepository(session)
            db_watched = repo.get(SETTING_WATCHED_DIRECTORIES)
            db_ignored = repo.get(SETTING_IGNORED_DIRECTORIES)
            db_ai = repo.get(SETTING_AI_EPITAPHS_ENABLED)
            if db_watched is not None:
                config.watched_directories = db_watched
            if db_ignored is not None:
                config.ignored_directories = db_ignored
            if db_ai is not None:
                config.ai_epitaphs_enabled = db_ai

        processor.update_directories(
            watched_directories=config.watched_directories,
            ignored_directories=config.ignored_directories,
        )
        for directory in config.watched_directories:
            try:
                watcher.add_directory(directory)
            except WatcherError as exc:
                logger.warning("Skipping configured directory: %s", exc)

        watcher.start()
        yield
        watcher.stop()
        database.dispose()
        logger.info("Digital Cemetery backend shutting down")

    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
    )

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s %d %.1fms req_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["x-request-id"] = request_id
        return response

    app.state.config = config
    app.state.database = database
    app.state.lifecycle = processor.lifecycle
    app.state.watcher = watcher
    app.state.processor = processor

    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(deaths_router, prefix="/api/v1", tags=["deaths"])
    app.include_router(statistics_router, prefix="/api/v1", tags=["statistics"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])

    register_error_handlers(app)

    return app


app = create_app()
"""Error handling middleware and exception handlers."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger
from app.schemas.errors import ErrorDetail, ErrorResponse, ValidationErrorResponse

logger = get_logger(__name__)


class CemeteryError(Exception):
    """Base exception for application-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "error",
        field: str | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.field = field
        self.status_code = status_code


class NotFoundError(CemeteryError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, code="not_found", field=field, status_code=404)


class ValidationError(CemeteryError):
    def __init__(
        self, message: str, field: str | None = None, details: list[ErrorDetail] | None = None
    ) -> None:
        super().__init__(message, code="validation_error", field=field, status_code=400)
        self.details = details or []


async def cemetery_exception_handler(request: Request, exc: CemeteryError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    logger.warning(
        "CemeteryError: %s (code=%s, field=%s, path=%s)",
        exc.message,
        exc.code,
        exc.field,
        request.url.path,
    )
    details = []
    if exc.field:
        details.append(ErrorDetail(field=exc.field, message=exc.message, code=exc.code))
    elif hasattr(exc, "details"):
        details = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.code,
            message=exc.message,
            details=details,
            request_id=request_id,
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    logger.warning(
        "HTTPException: %s (status=%s, path=%s)", exc.detail, exc.status_code, request.url.path
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump(),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    logger.warning(
        "ValidationError: %s (path=%s)", exc.errors(), request.url.path
    )
    details = [
        ErrorDetail(
            field=".".join(str(loc) for loc in err["loc"][1:]),
            message=err["msg"],
            code=err["type"],
        )
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ValidationErrorResponse(
            error="validation_error",
            message="Request validation failed",
            details=details,
            request_id=request_id,
        ).model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    logger.exception("Unhandled exception: %s (path=%s)", exc, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            request_id=request_id,
        ).model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CemeteryError, cemetery_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
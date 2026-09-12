"""Error handling schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str | None = None
    message: str
    code: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    error: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class ValidationErrorResponse(ErrorResponse):
    error: str = "validation_error"
    details: list[ErrorDetail]


class NotFoundErrorResponse(ErrorResponse):
    error: str = "not_found"


class InternalErrorResponse(ErrorResponse):
    error: str = "internal_error"
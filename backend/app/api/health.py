"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Service health payload."""

    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Simple liveness check. Returns ``{'status': 'ok'}`` when the backend is up.",
    responses={
        200: {
            "description": "Backend is running",
            "content": {
                "application/json": {"example": {"status": "ok"}},
            },
        },
    },
)
def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")
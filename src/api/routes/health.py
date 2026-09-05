"""Health and system configuration routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import ConfigResponse, HealthResponse
from src.api.service import AeroService

router = APIRouter(tags=["System & Health"])


@router.get("/healthz", response_model=HealthResponse, summary="Service health check")
def get_health() -> HealthResponse:
    """Returns active service health status and Google Cloud configuration."""
    return AeroService.get_health()


@router.get("/api/config", response_model=ConfigResponse, summary="Inspect system configuration")
def get_config() -> ConfigResponse:
    """Returns runtime model tier, region, and diagnostic provider configurations."""
    return AeroService.get_config()

"""Diagnostic reasoning routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas import DiagnoseRequest, DiagnoseResponse
from src.api.service import AeroService

router = APIRouter(prefix="/api/diagnose", tags=["AI Diagnostic Engine"])


@router.post("", response_model=DiagnoseResponse, summary="Execute AI incident diagnosis and grounding check")
def diagnose_incident(req: DiagnoseRequest) -> DiagnoseResponse:
    """Performs multi-signal telemetry correlation, causal reasoning, and evidence grounding."""
    try:
        return AeroService.diagnose(req.incident, provider=req.provider)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Diagnostic reasoning failed: {e!s}")

"""API routes for AERO Pre-Deployment Risk Advisor."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.service import AeroService
from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.schemas.risk import RiskAnalysisRequest, RiskAnalysisResponse

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.post("/analyze", response_model=RiskAnalysisResponse)
async def analyze_change_risk(request: RiskAnalysisRequest) -> RiskAnalysisResponse:
    """Analyze a proposed deployment/configuration change for SRE stability risks."""
    # Validate service and description are non-empty
    if not request.proposed_change.service or not request.proposed_change.service.strip():
        raise HTTPException(
            status_code=400,
            detail="Proposed change 'service' name cannot be empty.",
        )

    if not request.proposed_change.description or not request.proposed_change.description.strip():
        raise HTTPException(
            status_code=400,
            detail="Proposed change 'description' cannot be empty.",
        )

    # Validate scenario_key if provided
    if request.scenario_key and request.scenario_key not in BENCHMARK_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{request.scenario_key}' not found.",
        )

    return AeroService.analyze_risk(request)


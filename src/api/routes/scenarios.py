"""Scenario discovery and retrieval routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import ScenarioSummaryResponse
from src.api.service import AeroService
from src.schemas.ground_truth import BenchmarkScenarioBundle

router = APIRouter(prefix="/api/scenarios", tags=["Benchmark Scenarios"])


@router.get("", response_model=list[ScenarioSummaryResponse], summary="List all benchmark scenarios")
def list_scenarios(seed: int = Query(default=42, description="Random seed")) -> list[ScenarioSummaryResponse]:
    """Returns summaries of all available ground-truth benchmark scenarios."""
    return AeroService.list_scenarios(seed=seed)


@router.get("/{scenario_key}", response_model=BenchmarkScenarioBundle, summary="Get scenario bundle with telemetry")
def get_scenario(scenario_key: str, seed: int = Query(default=42, description="Random seed")) -> BenchmarkScenarioBundle:
    """Returns the full ground-truth bundle and incident telemetry for a specific scenario."""
    try:
        return AeroService.get_scenario_bundle(scenario_key, seed=seed)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

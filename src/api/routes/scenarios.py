"""Scenario discovery and retrieval routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import ScenarioSummaryResponse
from src.api.service import AeroService
from src.schemas.ground_truth import BenchmarkScenarioBundle
from src.schemas.timeline import IncidentReplaySeries, IncidentTimeline

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


@router.get("/{scenario_key}/timeline", response_model=IncidentTimeline, summary="Get synthesized timeline for scenario")
def get_scenario_timeline(scenario_key: str, seed: int = Query(default=42, description="Random seed")) -> IncidentTimeline:
    """Returns the synthesized chronological timeline for a specific benchmark scenario."""
    try:
        bundle = AeroService.get_scenario_bundle(scenario_key, seed=seed)
        return AeroService.synthesize_timeline(bundle.incident)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{scenario_key}/replay", response_model=IncidentReplaySeries, summary="Get replay series for scenario")
def get_scenario_replay(
    scenario_key: str,
    interval_seconds: int = Query(default=60, description="Step interval in seconds"),
    seed: int = Query(default=42, description="Random seed"),
) -> IncidentReplaySeries:
    """Returns the ordered step-by-step state replay snapshots for a specific benchmark scenario."""
    try:
        bundle = AeroService.get_scenario_bundle(scenario_key, seed=seed)
        return AeroService.generate_replay(bundle.incident, interval_seconds=interval_seconds)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

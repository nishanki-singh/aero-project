"""Timeline synthesis and state replay routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import ReplayRequest, TimelineRequest
from src.api.service import AeroService
from src.schemas.timeline import IncidentReplaySeries, IncidentTimeline

router = APIRouter(prefix="/api/timeline", tags=["Timeline & Replay"])


@router.post("", response_model=IncidentTimeline, summary="Synthesize chronological incident timeline")
def synthesize_timeline(req: TimelineRequest) -> IncidentTimeline:
    """Synthesizes milestone events from incident telemetry and optional diagnostic report."""
    return AeroService.synthesize_timeline(req.incident, req.diagnostic_report)


@router.post("/replay", response_model=IncidentReplaySeries, summary="Generate step-by-step state replay snapshots")
def generate_replay(req: ReplayRequest) -> IncidentReplaySeries:
    """Discretizes incident observation window into 1-minute step snapshots."""
    return AeroService.generate_replay(req.incident, interval_seconds=req.interval_seconds)

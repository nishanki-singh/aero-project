"""FastAPI routes for Blast-Radius Topology and Synthetic Chaos Sandbox."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.api.service import AeroService
from src.schemas.topology import (
    BlastRadiusReport,
    ChaosExperimentRequest,
    ChaosSimulationResult,
    TopologyGraph,
)

router = APIRouter(prefix="/api/topology", tags=["Topology & Chaos Sandbox"])


@router.get(
    "",
    response_model=TopologyGraph,
    summary="Get Canonical Topology Graph",
    description="Returns the canonical 11-node / 18-edge microservice topology graph with observed incident telemetry mapping.",
)
async def get_topology(
    scenario_key: str | None = Query(
        default=None,
        description="Optional active benchmark scenario key to map observed incident states",
    ),
) -> TopologyGraph:
    """Fetches the architectural topology model with observed health state mappings."""
    return AeroService.get_topology(scenario_key=scenario_key)


@router.get(
    "/blast-radius/{service_id}",
    response_model=BlastRadiusReport,
    summary="Evaluate Service Blast-Radius",
    description="Dynamically computes upstream impact callers, cascade paths, and blast radius percentage for a target node.",
)
async def get_blast_radius(
    service_id: str,
    scenario_key: str | None = Query(
        default=None,
        description="Optional scenario key context",
    ),
) -> BlastRadiusReport:
    """Computes dynamic blast radius for a service in the topology."""
    return AeroService.get_blast_radius(service_id=service_id, scenario_key=scenario_key)


@router.post(
    "/chaos/simulate",
    response_model=ChaosSimulationResult,
    summary="Simulate Synthetic Chaos Experiment",
    description="Executes a pure, deterministic chaos simulation without mutating persistent state or external infrastructure.",
)
async def simulate_chaos(
    request: ChaosExperimentRequest,
) -> ChaosSimulationResult:
    """Runs a pure deterministic chaos simulation and returns failure propagation cascade."""
    return AeroService.simulate_chaos(request)



@router.post(
    "/chaos/reset",
    response_model=TopologyGraph,
    summary="Reset Chaos Simulation View",
    description="Restores the baseline topology graph and active scenario incident observed state.",
)
async def reset_chaos(
    scenario_key: str | None = Query(
        default=None,
        description="Active scenario key to restore baseline observed states",
    ),
) -> TopologyGraph:
    """Restores baseline observed state for the topology graph."""
    return AeroService.reset_chaos(scenario_key=scenario_key)

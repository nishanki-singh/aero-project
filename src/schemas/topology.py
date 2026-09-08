"""Pydantic schemas for AERO Phase 4 Stage 4H: Blast-Radius Topology & Synthetic Chaos Sandbox."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServiceTier(str, Enum):
    """Architectural classification tiers for microservices and datastores."""

    INGRESS = "INGRESS"
    TIER_1_CORE = "TIER_1_CORE"
    TIER_2_BACKEND = "TIER_2_BACKEND"
    DATASTORE = "DATASTORE"
    EXTERNAL = "EXTERNAL"


class NodeHealthState(str, Enum):
    """Operational and simulated health states for topology nodes."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    FAILED = "FAILED"
    SIMULATED_CHAOS = "SIMULATED_CHAOS"


class CriticalPathImpact(str, Enum):
    """Qualitative assessment of critical revenue path impact."""

    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChaosType(str, Enum):
    """Supported deterministic chaos experiment failure modes."""

    LATENCY_INJECTION = "LATENCY_INJECTION"
    PACKET_LOSS = "PACKET_LOSS"
    OOM_CRASH_SIMULATION = "OOM_CRASH_SIMULATION"
    DB_POOL_EXHAUSTION_SIMULATION = "DB_POOL_EXHAUSTION_SIMULATION"
    DOWNSTREAM_OUTAGE_SIMULATION = "DOWNSTREAM_OUTAGE_SIMULATION"
    CACHE_POISONING_CHAOS = "CACHE_POISONING_CHAOS"


class ServiceNode(BaseModel):
    """A node in the microservice topology graph."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique node identifier (e.g. checkout-service)")
    name: str = Field(..., description="Display name for UI visualization")
    tier: ServiceTier = Field(..., description="Architectural layer tier")
    status: NodeHealthState = Field(default=NodeHealthState.HEALTHY, description="Current health status")
    is_observed_incident_state: bool = Field(
        default=True,
        description="True if derived from active scenario telemetry; False if simulated chaos output",
    )
    metrics: dict[str, Any] = Field(default_factory=dict, description="Key operational telemetry signals")
    criticality: str = Field(default="MEDIUM", description="Business criticality tier (CRITICAL, HIGH, MEDIUM, LOW)")
    description: str = Field(default="", description="Functional role of the service/datastore")
    is_external: bool = Field(default=False, description="Whether node is an external 3rd-party dependency")
    is_datastore: bool = Field(default=False, description="Whether node is a database, cache, or queue")
    layer_index: int = Field(default=1, description="Vertical/horizontal layer index for visual layout (0 to 3)")


class DependencyEdge(BaseModel):
    """A directed communication dependency between two topology nodes."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(..., description="Source / caller service ID")
    target: str = Field(..., description="Target / downstream dependency ID")
    protocol: str = Field(default="HTTP/REST", description="Communication protocol (HTTP/REST, gRPC, TCP/SQL, etc.)")
    is_critical: bool = Field(default=True, description="Whether this is a hard blocking dependency vs soft cache fallback")
    timeout_ms: int = Field(default=3000, description="Configured RPC / socket timeout in milliseconds")
    circuit_breaker: bool = Field(default=False, description="Whether client-side circuit breaking is enabled")
    status: str = Field(default="NORMAL", description="Status of edge: NORMAL, DEGRADED, SEVERED, or SATURATED")


class TopologyGraph(BaseModel):
    """Complete architectural microservice topology graph."""

    model_config = ConfigDict(extra="ignore")

    nodes: list[ServiceNode] = Field(default_factory=list, description="All service and datastore nodes")
    edges: list[DependencyEdge] = Field(default_factory=list, description="All directed dependency edges")
    active_incident_service: str | None = Field(
        default=None,
        description="Primary affected service from active incident scenario (if applicable)",
    )
    scenario_key: str | None = Field(
        default=None,
        description="Active scenario key providing baseline telemetry mapping",
    )
    is_synthetic_model: bool = Field(
        default=True,
        description="Explicit indicator that this is an architectural benchmark model",
    )


class BlastRadiusReport(BaseModel):
    """Dynamically computed blast-radius evaluation for a target node."""

    model_config = ConfigDict(extra="ignore")

    target_service: str = Field(..., description="Target service/datastore evaluated")
    direct_upstream: list[str] = Field(default_factory=list, description="Services directly calling target (1-hop)")
    transitive_upstream: list[str] = Field(
        default_factory=list,
        description="Indirectly affected upstream services (2+ hops up to ingress)",
    )
    direct_downstream: list[str] = Field(default_factory=list, description="Services called by target")
    total_impacted_services: int = Field(..., description="Total count of uniquely impacted nodes (target + upstreams)")
    total_nodes_in_system: int = Field(default=11, description="Total nodes in the topology")
    blast_radius_pct: float = Field(..., description="Percentage of total system impacted (0.0 to 100.0%)")
    impact_level: str = Field(..., description="Qualitative impact level: ISOLATED, MODERATE, HIGH, CATASTROPHIC")
    critical_path_breached: bool = Field(..., description="True if core checkout/payment/auth flow is compromised")
    cascade_paths: list[list[str]] = Field(
        default_factory=list,
        description="Ordered failure cascade paths from target to ingress or dependent services",
    )
    critical_path_impact: CriticalPathImpact = Field(
        default=CriticalPathImpact.NONE,
        description="Qualitative critical path impact classification",
    )


class ChaosExperimentRequest(BaseModel):
    """Request payload to simulate a synthetic chaos experiment."""

    model_config = ConfigDict(extra="ignore")

    target_service: str = Field(..., description="Target node for fault injection")
    chaos_type: ChaosType = Field(..., description="Fault injection mode")
    magnitude: int | None = Field(default=None, description="Fault magnitude (e.g. latency in ms or pool size)")
    scenario_key: str | None = Field(default=None, description="Active scenario context for baseline state")


class ChaosSimulationResult(BaseModel):
    """Deterministic simulation results of a synthetic chaos experiment."""

    model_config = ConfigDict(extra="ignore")

    experiment_id: str = Field(..., description="Deterministic experiment identifier")
    target_service: str = Field(..., description="Target node injected with fault")
    chaos_type: ChaosType = Field(..., description="Injected chaos experiment type")
    propagated_node_states: dict[str, NodeHealthState] = Field(
        default_factory=dict,
        description="Propagated simulated health states per node ID",
    )
    propagated_edge_states: dict[str, str] = Field(
        default_factory=dict,
        description="Propagated edge status keyed by 'source->target'",
    )
    blast_radius: BlastRadiusReport = Field(..., description="Dynamic blast radius calculated from propagated failure")
    propagation_steps: list[str] = Field(
        default_factory=list,
        description="Step-by-step causal chain of failure propagation",
    )
    resilience_findings: list[str] = Field(
        default_factory=list,
        description="Architectural resilience takeaways and preventive recommendations",
    )
    is_synthetic_simulation: bool = Field(
        default=True,
        description="Explicit indicator that this is a synthetic simulation output",
    )

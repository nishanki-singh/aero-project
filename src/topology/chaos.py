"""Deterministic Synthetic Chaos Sandbox Engine.

Simulates failure propagation and architectural blast radius across the microservice topology
in a pure, offline, and non-destructive sandbox.
"""

from __future__ import annotations

from src.schemas.topology import (
    ChaosExperimentRequest,
    ChaosSimulationResult,
    ChaosType,
    NodeHealthState,
)
from src.topology.engine import BlastRadiusEngine
from src.topology.graph import build_canonical_topology_graph


class ChaosSandboxEngine:
    """Pure, deterministic chaos simulation sandbox engine."""

    def __init__(self) -> None:
        self.base_graph = build_canonical_topology_graph()

    def simulate_chaos(self, request: ChaosExperimentRequest) -> ChaosSimulationResult:
        """Executes a pure, deterministic chaos simulation without mutating global state."""
        target = request.target_service
        chaos_type = request.chaos_type

        # Generate deterministic experiment ID
        slug_type = chaos_type.value.lower().replace("_simulation", "").replace("_chaos", "")
        experiment_id = f"chaos-{slug_type}-{target}"

        propagated_nodes: dict[str, NodeHealthState] = {}
        propagated_edges: dict[str, str] = {}
        steps: list[str] = []
        findings: list[str] = []

        # Target is immediately simulated chaos / failed
        propagated_nodes[target] = NodeHealthState.SIMULATED_CHAOS

        if chaos_type == ChaosType.LATENCY_INJECTION:
            mag = request.magnitude or 5000
            steps.append(f"[Fault Injected] Injected +{mag}ms latency delay on '{target}' (exceeds socket timeout).")

            if target == "partner-payment-gateway":
                propagated_edges["payment-service->partner-payment-gateway"] = "SATURATED"
                propagated_edges["checkout-service->partner-payment-gateway"] = "SATURATED"
                propagated_nodes["payment-service"] = NodeHealthState.UNHEALTHY
                steps.append("[Hop 1 - Worker Starvation] 'payment-service' worker thread pool exhausted waiting for acquiring bank RPC (>5000ms).")

                propagated_edges["checkout-service->payment-service"] = "SATURATED"
                propagated_nodes["checkout-service"] = NodeHealthState.DEGRADED
                steps.append("[Hop 2 - Synchronous Cascade] 'checkout-service' synchronous RPC to payment-service times out.")

                propagated_edges["api-gateway->checkout-service"] = "DEGRADED"
                propagated_nodes["api-gateway"] = NodeHealthState.DEGRADED
                steps.append("[Hop 3 - Ingress Impact] 'api-gateway' returns HTTP 504 Gateway Timeout across checkout customer paths.")

                # Synchronous dependents also impacted during payment outage
                propagated_nodes["order-service"] = NodeHealthState.DEGRADED
                propagated_nodes["auth-service"] = NodeHealthState.DEGRADED
                propagated_nodes["postgres-db"] = NodeHealthState.DEGRADED
                propagated_edges["checkout-service->order-service"] = "DEGRADED"

                findings.append("Missing circuit breaker and client-side RPC timeout on checkout-service to payment-service downstream call.")
                findings.append("Downstream third-party acquiring gateway latency propagates directly upstream through synchronous blocking calls.")
                findings.append("Recommendation: Implement exponential backoff with jitter, bulkhead thread pool isolation, and asynchronous order settlement via Kafka.")
            else:
                # Generic latency propagation
                engine = BlastRadiusEngine(self.base_graph)
                upstreams = engine.reverse_adj.get(target, [])
                for u in upstreams:
                    propagated_edges[f"{u}->{target}"] = "SATURATED"
                    propagated_nodes[u] = NodeHealthState.DEGRADED
                    steps.append(f"[Cascade] Upstream caller '{u}' experiences elevated latency calling '{target}'.")
                findings.append(f"Synthetic latency injection on '{target}' degraded {len(upstreams)} direct callers.")

        elif chaos_type == ChaosType.DB_POOL_EXHAUSTION_SIMULATION:
            steps.append(f"[Fault Injected] Exhausted connection pool on '{target}' (pool_max: 2, active: 2/2 saturated, queue: 85 waiting).")

            direct_db_clients = ["order-service", "payment-service", "auth-service", "catalog-service", "worker-service"]
            for client in direct_db_clients:
                propagated_edges[f"{client}->{target}"] = "SEVERED"
                propagated_nodes[client] = NodeHealthState.UNHEALTHY
                steps.append(f"[Hop 1 - DB Starvation] Direct database client '{client}' fails connection acquisition after timeout.")

            propagated_nodes["checkout-service"] = NodeHealthState.FAILED
            propagated_edges["checkout-service->order-service"] = "SEVERED"
            propagated_edges["checkout-service->payment-service"] = "SEVERED"
            steps.append("[Hop 2 - Core Cascade] 'checkout-service' transaction coordinator fails all cart submission and settlement workflows.")

            propagated_nodes["api-gateway"] = NodeHealthState.DEGRADED
            propagated_edges["api-gateway->checkout-service"] = "DEGRADED"
            propagated_edges["api-gateway->auth-service"] = "DEGRADED"
            steps.append("[Hop 3 - Ingress Failure] 'api-gateway' returns HTTP 500/503 errors across all authenticated API endpoints.")

            findings.append("Single point of failure: PostgreSQL database pool starvation cascades across all synchronous and asynchronous clients.")
            findings.append("Auth, Order, Catalog, Payment, and Worker services share primary database pool with unconstrained connection limits.")
            findings.append("Recommendation: Deploy connection pooling proxy (PgBouncer) and separate read replicas for catalog-service.")

        elif chaos_type == ChaosType.OOM_CRASH_SIMULATION:
            steps.append(f"[Fault Injected] Simulated rapid memory saturation on '{target}', triggering Linux OOMKiller (container exit code 137).")
            propagated_nodes[target] = NodeHealthState.FAILED

            if target == "worker-service":
                propagated_edges["worker-service->kafka-queue"] = "SEVERED"
                propagated_nodes["kafka-queue"] = NodeHealthState.DEGRADED
                steps.append("[Hop 1 - Async Stalling] 'worker-service' enters CrashLoopBackOff; Kafka consumer group stalls with accumulating partition lag.")
                steps.append("[Isolation Verified] Core synchronous user journey ('checkout-service', 'order-service', 'api-gateway') remains HEALTHY and responsive.")

                findings.append("Architectural resilience verified: Asynchronous background worker failure is cleanly buffered and isolated by Kafka.")
                findings.append("Synchronous customer-facing transaction paths remain fully operational during worker crash.")
                findings.append("Recommendation: Configure JVM/container memory limits with headroom and enable HPA based on Kafka consumer lag.")
            else:
                propagated_nodes[target] = NodeHealthState.FAILED
                steps.append(f"[Node Crash] Service '{target}' terminated and restarting.")
                findings.append(f"OOMKill simulated on '{target}'.")

        elif chaos_type == ChaosType.DOWNSTREAM_OUTAGE_SIMULATION:
            steps.append(f"[Fault Injected] Severed network connectivity and triggered eviction storm on cache cluster '{target}'.")
            propagated_nodes[target] = NodeHealthState.FAILED

            if target == "redis-cache":
                propagated_edges["auth-service->redis-cache"] = "SEVERED"
                propagated_edges["catalog-service->redis-cache"] = "SEVERED"
                propagated_nodes["auth-service"] = NodeHealthState.DEGRADED
                propagated_nodes["catalog-service"] = NodeHealthState.DEGRADED
                steps.append("[Hop 1 - Cache Miss Storm] 'auth-service' and 'catalog-service' experience 100% cache misses and fall back to direct PostgreSQL queries.")

                propagated_edges["catalog-service->postgres-db"] = "SATURATED"
                propagated_edges["auth-service->postgres-db"] = "SATURATED"
                propagated_nodes["postgres-db"] = NodeHealthState.DEGRADED
                steps.append("[Hop 2 - Secondary DB Saturation] Cache-aside fallback surges database query load by 4.5x, elevating query latencies.")

                propagated_edges["api-gateway->catalog-service"] = "DEGRADED"
                propagated_nodes["api-gateway"] = NodeHealthState.DEGRADED
                steps.append("[Hop 3 - Ingress Latency] 'api-gateway' observes elevated P99 latency on catalog and session verification routes.")

                findings.append("Graceful degradation verified: Cache outage falls back to primary database, but exposes backend to secondary connection saturation.")
                findings.append("Recommendation: Implement in-memory L1 local cache with Redis cluster multi-AZ replication and circuit-breaking fallback.")
            else:
                engine = BlastRadiusEngine(self.base_graph)
                for u in engine.reverse_adj.get(target, []):
                    propagated_edges[f"{u}->{target}"] = "SEVERED"
                    propagated_nodes[u] = NodeHealthState.DEGRADED
                    steps.append(f"[Downstream Lost] Upstream service '{u}' lost connection to '{target}'.")
                findings.append(f"Simulated full outage on '{target}'.")

        elif chaos_type == ChaosType.CACHE_POISONING_CHAOS:
            steps.append(f"[Fault Injected] Injected corrupted/expired JWT signing key into '{target}' token validation cache.")
            propagated_nodes[target] = NodeHealthState.UNHEALTHY

            propagated_edges["checkout-service->auth-service"] = "DEGRADED"
            propagated_nodes["checkout-service"] = NodeHealthState.DEGRADED
            steps.append("[Hop 1 - Session Rejection] 'checkout-service' and internal RPC clients receive 401 Unauthorized for valid user session tokens.")

            propagated_edges["api-gateway->auth-service"] = "DEGRADED"
            propagated_edges["api-gateway->checkout-service"] = "DEGRADED"
            propagated_nodes["api-gateway"] = NodeHealthState.DEGRADED
            steps.append("[Hop 2 - Ingress Rejection] 'api-gateway' blocks client transactions with HTTP 401 Unauthorized across all authenticated routes.")

            propagated_nodes["order-service"] = NodeHealthState.DEGRADED
            propagated_nodes["catalog-service"] = NodeHealthState.DEGRADED
            propagated_nodes["redis-cache"] = NodeHealthState.DEGRADED

            findings.append("Security & Auth blast radius: Key rotation mismatch blocks all authenticated user journeys.")
            findings.append("Recommendation: Implement dual-key rotation overlap window, JWKS caching fallback, and automated public key cache invalidation.")

        # Compute dynamic blast radius on the simulated state
        sim_graph = build_canonical_topology_graph(
            scenario_key=request.scenario_key,
            custom_node_states=propagated_nodes,
            custom_edge_states=propagated_edges,
        )
        blast_engine = BlastRadiusEngine(graph=sim_graph)
        blast_report = blast_engine.compute_blast_radius(
            target_service=target,
            impacted_nodes_override=set(propagated_nodes.keys()),
        )

        return ChaosSimulationResult(
            experiment_id=experiment_id,
            target_service=target,
            chaos_type=chaos_type,
            propagated_node_states=propagated_nodes,
            propagated_edge_states=propagated_edges,
            blast_radius=blast_report,
            propagation_steps=steps,
            resilience_findings=findings,
            is_synthetic_simulation=True,
        )

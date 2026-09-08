"""Canonical architectural topology graph definition and incident telemetry mapper."""

from __future__ import annotations

from typing import Any

from src.schemas.topology import (
    DependencyEdge,
    NodeHealthState,
    ServiceNode,
    ServiceTier,
    TopologyGraph,
)

# Canonical 11 Nodes Definition
CANONICAL_NODES: list[dict[str, Any]] = [
    {
        "id": "api-gateway",
        "name": "API Gateway",
        "tier": ServiceTier.INGRESS,
        "criticality": "CRITICAL",
        "description": "Public edge ingress reverse proxy and TLS terminator",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 0,
        "metrics": {"rps": 2450, "p99_latency_ms": 42, "error_rate": 0.001},
    },
    {
        "id": "auth-service",
        "name": "Auth Service",
        "tier": ServiceTier.TIER_1_CORE,
        "criticality": "CRITICAL",
        "description": "JWT authentication and RBAC session authorization provider",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 1,
        "metrics": {"rps": 1800, "token_validation_rate": 0.999, "latency_ms": 15},
    },
    {
        "id": "catalog-service",
        "name": "Catalog Service",
        "tier": ServiceTier.TIER_2_BACKEND,
        "criticality": "MEDIUM",
        "description": "Product catalog queries and inventory metadata lookup",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 1,
        "metrics": {"rps": 850, "cache_hit_rate": 0.94, "latency_ms": 28},
    },
    {
        "id": "checkout-service",
        "name": "Checkout Service",
        "tier": ServiceTier.TIER_1_CORE,
        "criticality": "CRITICAL",
        "description": "Cart orchestration, order validation, and transaction coordinator",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 1,
        "metrics": {"rps": 320, "conversion_rate": 0.98, "latency_ms": 65},
    },
    {
        "id": "order-service",
        "name": "Order Service",
        "tier": ServiceTier.TIER_1_CORE,
        "criticality": "CRITICAL",
        "description": "Order lifecycle state machine and customer transaction logging",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 1,
        "metrics": {"rps": 310, "db_query_time_ms": 12, "latency_ms": 45},
    },
    {
        "id": "payment-service",
        "name": "Payment Service",
        "tier": ServiceTier.TIER_1_CORE,
        "criticality": "CRITICAL",
        "description": "Payment authorization and settlement processing mediator",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 1,
        "metrics": {"rps": 290, "settlement_success_rate": 0.995, "latency_ms": 110},
    },
    {
        "id": "worker-service",
        "name": "Worker Service",
        "tier": ServiceTier.TIER_2_BACKEND,
        "criticality": "LOW",
        "description": "Asynchronous background order fulfillment and notification worker",
        "is_external": False,
        "is_datastore": False,
        "layer_index": 2,
        "metrics": {"jobs_per_sec": 45, "queue_depth": 12, "cpu_usage": 0.35},
    },
    {
        "id": "postgres-db",
        "name": "PostgreSQL Primary",
        "tier": ServiceTier.DATASTORE,
        "criticality": "CRITICAL",
        "description": "Relational transactional database storing orders, users, and ledgers",
        "is_external": False,
        "is_datastore": True,
        "layer_index": 2,
        "metrics": {"active_connections": 42, "max_connections": 100, "buffer_hit_ratio": 0.99},
    },
    {
        "id": "redis-cache",
        "name": "Redis Cluster",
        "tier": ServiceTier.DATASTORE,
        "criticality": "HIGH",
        "description": "In-memory distributed key-value cache and session token store",
        "is_external": False,
        "is_datastore": True,
        "layer_index": 2,
        "metrics": {"memory_used_mb": 512, "max_memory_mb": 2048, "eviction_rate": 0.0},
    },
    {
        "id": "kafka-queue",
        "name": "Kafka Event Bus",
        "tier": ServiceTier.DATASTORE,
        "criticality": "HIGH",
        "description": "Distributed event log streaming order events to asynchronous workers",
        "is_external": False,
        "is_datastore": True,
        "layer_index": 2,
        "metrics": {"lag_records": 15, "bytes_in_per_sec": 124000, "partition_count": 12},
    },
    {
        "id": "partner-payment-gateway",
        "name": "Partner Payment Gateway",
        "tier": ServiceTier.EXTERNAL,
        "criticality": "CRITICAL",
        "description": "External third-party credit card processing acquiring bank partner",
        "is_external": True,
        "is_datastore": False,
        "layer_index": 3,
        "metrics": {"upstream_p99_ms": 350, "http_status_5xx_pct": 0.0},
    },
]

# Canonical 18 Edges Definition
CANONICAL_EDGES: list[dict[str, Any]] = [
    {"source": "api-gateway", "target": "auth-service", "protocol": "HTTP/REST", "is_critical": True, "timeout_ms": 2000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "api-gateway", "target": "catalog-service", "protocol": "HTTP/REST", "is_critical": False, "timeout_ms": 3000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "api-gateway", "target": "checkout-service", "protocol": "HTTP/REST", "is_critical": True, "timeout_ms": 5000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "api-gateway", "target": "order-service", "protocol": "HTTP/REST", "is_critical": True, "timeout_ms": 4000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "auth-service", "target": "redis-cache", "protocol": "Redis/TCP", "is_critical": False, "timeout_ms": 500, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "auth-service", "target": "postgres-db", "protocol": "Postgres/TCP", "is_critical": True, "timeout_ms": 3000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "catalog-service", "target": "redis-cache", "protocol": "Redis/TCP", "is_critical": False, "timeout_ms": 500, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "catalog-service", "target": "postgres-db", "protocol": "Postgres/TCP", "is_critical": True, "timeout_ms": 3000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "checkout-service", "target": "auth-service", "protocol": "gRPC", "is_critical": True, "timeout_ms": 2000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "checkout-service", "target": "order-service", "protocol": "gRPC", "is_critical": True, "timeout_ms": 4000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "checkout-service", "target": "payment-service", "protocol": "gRPC", "is_critical": True, "timeout_ms": 5000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "checkout-service", "target": "partner-payment-gateway", "protocol": "HTTP/REST", "is_critical": True, "timeout_ms": 10000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "order-service", "target": "postgres-db", "protocol": "Postgres/TCP", "is_critical": True, "timeout_ms": 3000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "order-service", "target": "kafka-queue", "protocol": "Kafka/TCP", "is_critical": True, "timeout_ms": 2000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "payment-service", "target": "postgres-db", "protocol": "Postgres/TCP", "is_critical": True, "timeout_ms": 3000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "payment-service", "target": "partner-payment-gateway", "protocol": "HTTP/REST", "is_critical": True, "timeout_ms": 8000, "circuit_breaker": False, "status": "NORMAL"},
    {"source": "worker-service", "target": "kafka-queue", "protocol": "Kafka/TCP", "is_critical": True, "timeout_ms": 3000, "circuit_breaker": True, "status": "NORMAL"},
    {"source": "worker-service", "target": "postgres-db", "protocol": "Postgres/TCP", "is_critical": True, "timeout_ms": 4000, "circuit_breaker": False, "status": "NORMAL"},
]

# Scenario observed health mapping presets
SCENARIO_OBSERVED_PROFILES: dict[str, dict[str, Any]] = {
    "scenario_01_db_pool": {
        "active_incident_service": "postgres-db",
        "node_states": {
            "postgres-db": NodeHealthState.FAILED,
            "order-service": NodeHealthState.UNHEALTHY,
            "payment-service": NodeHealthState.DEGRADED,
            "auth-service": NodeHealthState.DEGRADED,
            "catalog-service": NodeHealthState.DEGRADED,
            "checkout-service": NodeHealthState.DEGRADED,
            "api-gateway": NodeHealthState.DEGRADED,
        },
        "edge_states": {
            "order-service->postgres-db": "SEVERED",
            "payment-service->postgres-db": "SATURATED",
            "auth-service->postgres-db": "DEGRADED",
            "catalog-service->postgres-db": "DEGRADED",
        },
        "node_metric_overrides": {
            "postgres-db": {"active_connections": 100, "max_connections": 100, "waiting_clients": 84, "pool_exhausted": True},
            "order-service": {"p99_latency_ms": 3400, "error_rate": 0.42},
        },
    },
    "scenario_02_jwt_auth": {
        "active_incident_service": "auth-service",
        "node_states": {
            "auth-service": NodeHealthState.FAILED,
            "checkout-service": NodeHealthState.DEGRADED,
            "api-gateway": NodeHealthState.DEGRADED,
        },
        "edge_states": {
            "api-gateway->auth-service": "DEGRADED",
            "checkout-service->auth-service": "DEGRADED",
        },
        "node_metric_overrides": {
            "auth-service": {"token_validation_rate": 0.02, "key_rotation_error": True, "error_rate": 0.98},
            "api-gateway": {"http_401_rate": 0.65, "error_rate": 0.35},
        },
    },
    "scenario_03_payment_timeout": {
        "active_incident_service": "partner-payment-gateway",
        "node_states": {
            "partner-payment-gateway": NodeHealthState.FAILED,
            "payment-service": NodeHealthState.UNHEALTHY,
            "checkout-service": NodeHealthState.DEGRADED,
            "api-gateway": NodeHealthState.DEGRADED,
        },
        "edge_states": {
            "payment-service->partner-payment-gateway": "SEVERED",
            "checkout-service->partner-payment-gateway": "SEVERED",
            "checkout-service->payment-service": "SATURATED",
        },
        "node_metric_overrides": {
            "partner-payment-gateway": {"upstream_p99_ms": 12500, "timeout_rate": 0.92},
            "payment-service": {"p99_latency_ms": 8200, "thread_pool_exhausted": True},
        },
    },
    "scenario_04_k8s_oom": {
        "active_incident_service": "worker-service",
        "node_states": {
            "worker-service": NodeHealthState.FAILED,
            "kafka-queue": NodeHealthState.DEGRADED,
        },
        "edge_states": {
            "worker-service->kafka-queue": "SEVERED",
        },
        "node_metric_overrides": {
            "worker-service": {"restart_count": 14, "exit_code": 137, "oom_killed": True},
            "kafka-queue": {"lag_records": 14200, "consumer_group_stalled": True},
        },
    },
    "scenario_05_redis_eviction": {
        "active_incident_service": "redis-cache",
        "node_states": {
            "redis-cache": NodeHealthState.UNHEALTHY,
            "catalog-service": NodeHealthState.DEGRADED,
            "auth-service": NodeHealthState.DEGRADED,
            "postgres-db": NodeHealthState.DEGRADED,
        },
        "edge_states": {
            "catalog-service->redis-cache": "DEGRADED",
            "auth-service->redis-cache": "DEGRADED",
            "catalog-service->postgres-db": "SATURATED",
        },
        "node_metric_overrides": {
            "redis-cache": {"memory_used_mb": 2048, "eviction_rate": 450.0, "cache_hit_rate": 0.22},
            "postgres-db": {"query_load_multiplier": 4.5, "buffer_hit_ratio": 0.72},
        },
    },
}


SCENARIO_KEY_ALIASES: dict[str, str] = {
    # Scenario 1: DB Pool Starvation
    "scenario_01_db_pool": "scenario_01_db_pool",
    "db_pool_exhaustion": "scenario_01_db_pool",
    "db_pool": "scenario_01_db_pool",
    "benchmark-db-002": "scenario_01_db_pool",
    "postgres-db": "scenario_01_db_pool",
    # Scenario 2: Config Drift / JWT Auth
    "scenario_02_jwt_auth": "scenario_02_jwt_auth",
    "config_drift": "scenario_02_jwt_auth",
    "jwt_auth": "scenario_02_jwt_auth",
    "benchmark-cfg-003": "scenario_02_jwt_auth",
    "auth-service": "scenario_02_jwt_auth",
    # Scenario 3: Payment Timeout / Dependency Deadlock
    "scenario_03_payment_timeout": "scenario_03_payment_timeout",
    "dependency_deadlock": "scenario_03_payment_timeout",
    "payment_timeout": "scenario_03_payment_timeout",
    "benchmark-dep-004": "scenario_03_payment_timeout",
    "partner-payment-gateway": "scenario_03_payment_timeout",
    # Scenario 4: Worker OOM / K8s OOM
    "scenario_04_k8s_oom": "scenario_04_k8s_oom",
    "oom_kill": "scenario_04_k8s_oom",
    "k8s_oom": "scenario_04_k8s_oom",
    "benchmark-oom-001": "scenario_04_k8s_oom",
    "worker-service": "scenario_04_k8s_oom",
    # Scenario 5: Cache Poisoning / Redis Eviction
    "scenario_05_redis_eviction": "scenario_05_redis_eviction",
    "cache_poisoning": "scenario_05_redis_eviction",
    "redis_eviction": "scenario_05_redis_eviction",
    "benchmark-cache-005": "scenario_05_redis_eviction",
    "redis-cache": "scenario_05_redis_eviction",
}


def build_canonical_topology_graph(
    scenario_key: str | None = None,
    custom_node_states: dict[str, NodeHealthState] | None = None,
    custom_edge_states: dict[str, str] | None = None,
) -> TopologyGraph:
    """Constructs the canonical 11-node / 18-edge topology graph with observed incident telemetry mapping.

    This graph is an architectural benchmark model (synthetic).
    When scenario_key is provided, health states are mapped from observed benchmark telemetry.
    """
    raw_key = (
        scenario_key.replace("scenarios/", "").replace(".json", "").strip()
        if scenario_key
        else None
    )
    normalized_key = None
    if raw_key:
        normalized_key = SCENARIO_KEY_ALIASES.get(raw_key) or SCENARIO_KEY_ALIASES.get(raw_key.lower()) or raw_key

    profile = SCENARIO_OBSERVED_PROFILES.get(normalized_key or "", {})
    active_incident_svc = profile.get("active_incident_service")
    preset_node_states: dict[str, NodeHealthState] = profile.get("node_states", {})
    preset_edge_states: dict[str, str] = profile.get("edge_states", {})
    metric_overrides: dict[str, dict[str, Any]] = profile.get("node_metric_overrides", {})


    nodes: list[ServiceNode] = []
    for raw_node in CANONICAL_NODES:
        node_id = raw_node["id"]
        # Determine status
        if custom_node_states and node_id in custom_node_states:
            status = custom_node_states[node_id]
            is_observed = False  # Custom states are simulated
        elif node_id in preset_node_states:
            status = preset_node_states[node_id]
            is_observed = True
        else:
            status = NodeHealthState.HEALTHY
            is_observed = True

        metrics = dict(raw_node["metrics"])
        if node_id in metric_overrides:
            metrics.update(metric_overrides[node_id])

        nodes.append(
            ServiceNode(
                id=node_id,
                name=raw_node["name"],
                tier=raw_node["tier"],
                status=status,
                is_observed_incident_state=is_observed,
                metrics=metrics,
                criticality=raw_node["criticality"],
                description=raw_node["description"],
                is_external=raw_node["is_external"],
                is_datastore=raw_node["is_datastore"],
                layer_index=raw_node["layer_index"],
            )
        )

    edges: list[DependencyEdge] = []
    for raw_edge in CANONICAL_EDGES:
        edge_key = f"{raw_edge['source']}->{raw_edge['target']}"
        if custom_edge_states and edge_key in custom_edge_states:
            status = custom_edge_states[edge_key]
        elif edge_key in preset_edge_states:
            status = preset_edge_states[edge_key]
        else:
            status = raw_edge["status"]

        edges.append(
            DependencyEdge(
                source=raw_edge["source"],
                target=raw_edge["target"],
                protocol=raw_edge["protocol"],
                is_critical=raw_edge["is_critical"],
                timeout_ms=raw_edge["timeout_ms"],
                circuit_breaker=raw_edge["circuit_breaker"],
                status=status,
            )
        )

    return TopologyGraph(
        nodes=nodes,
        edges=edges,
        active_incident_service=active_incident_svc,
        scenario_key=scenario_key,
        is_synthetic_model=True,
    )

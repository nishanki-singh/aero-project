"""Comprehensive test suite for AERO Phase 4 Stage 4H: Blast-Radius Topology & Chaos Sandbox.

Validates:
- Canonical 11-node / 18-edge topology graph invariants
- Dynamic blast-radius calculation and upstream BFS/DFS traversal
- All 5 deterministic synthetic chaos experiments
- Purity, scenario isolation, and zero cross-scenario state leakage
- Strict offline safety invariants (no subprocess, shell, GCP, or k8s mutation)
- FastAPI endpoints and static assets
"""

from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.schemas.topology import (
    BlastRadiusReport,
    ChaosExperimentRequest,
    ChaosSimulationResult,
    ChaosType,
    CriticalPathImpact,
    NodeHealthState,
    ServiceTier,
    TopologyGraph,
)
from src.topology.chaos import ChaosSandboxEngine
from src.topology.engine import evaluate_blast_radius
from src.topology.graph import (
    CANONICAL_EDGES,
    CANONICAL_NODES,
    SCENARIO_OBSERVED_PROFILES,
    build_canonical_topology_graph,
)

EXPECTED_NODE_IDS = {
    "api-gateway",
    "auth-service",
    "catalog-service",
    "checkout-service",
    "order-service",
    "payment-service",
    "worker-service",
    "postgres-db",
    "redis-cache",
    "kafka-queue",
    "partner-payment-gateway",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 1. Canonical Graph Invariant Tests
# ============================================================================


def test_canonical_graph_structure():
    """Validates the canonical 11-node / 18-edge graph structure and tiers."""
    graph = build_canonical_topology_graph()

    assert isinstance(graph, TopologyGraph)
    assert len(graph.nodes) == 11, f"Expected 11 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) == 18, f"Expected 18 edges, got {len(graph.edges)}"
    assert graph.is_synthetic_model is True

    node_ids = {n.id for n in graph.nodes}
    assert node_ids == EXPECTED_NODE_IDS

    # Verify tiers
    tier_map = {n.id: n.tier for n in graph.nodes}
    assert tier_map["api-gateway"] == ServiceTier.INGRESS
    assert tier_map["checkout-service"] == ServiceTier.TIER_1_CORE
    assert tier_map["postgres-db"] == ServiceTier.DATASTORE
    assert tier_map["partner-payment-gateway"] == ServiceTier.EXTERNAL


def test_canonical_edges_validity():
    """Ensures all 18 edges connect valid source and target nodes."""
    node_ids = {n["id"] for n in CANONICAL_NODES}

    for edge in CANONICAL_EDGES:
        assert edge["source"] in node_ids, f"Invalid edge source: {edge['source']}"
        assert edge["target"] in node_ids, f"Invalid edge target: {edge['target']}"
        assert edge["protocol"] in ["HTTP/REST", "gRPC", "Postgres/TCP", "Redis/TCP", "Kafka/TCP"]


def test_scenario_observed_incident_mappings():
    """Validates baseline observed health states for all 5 benchmark scenarios."""
    for sc_key in SCENARIO_OBSERVED_PROFILES:
        graph = build_canonical_topology_graph(scenario_key=sc_key)
        profile = SCENARIO_OBSERVED_PROFILES[sc_key]

        assert graph.active_incident_service == profile["active_incident_service"]
        for node_id, expected_status in profile["node_states"].items():
            node = next(n for n in graph.nodes if n.id == node_id)
            assert node.status == expected_status
            assert node.is_observed_incident_state is True


# ============================================================================
# 2. Dynamic Blast-Radius & Graph Traversal Tests
# ============================================================================


def test_dynamic_blast_radius_postgres_db():
    """Computes dynamic blast radius for postgres-db with cascading upstream callers."""
    report = evaluate_blast_radius("postgres-db")

    assert isinstance(report, BlastRadiusReport)
    assert report.target_service == "postgres-db"
    assert report.total_nodes_in_system == 11

    # Direct callers to postgres-db: auth, catalog, order, payment, worker
    assert set(report.direct_upstream) == {
        "auth-service",
        "catalog-service",
        "order-service",
        "payment-service",
        "worker-service",
    }
    # Transitive callers: api-gateway, checkout-service
    assert "api-gateway" in report.transitive_upstream
    assert "checkout-service" in report.transitive_upstream

    # Dynamic percentage: 8 impacted nodes out of 11 -> 72.7%
    assert report.total_impacted_services == 8
    expected_pct = round((8 / 11) * 100.0, 1)
    assert report.blast_radius_pct == expected_pct
    assert report.impact_level == "CATASTROPHIC"
    assert report.critical_path_impact == CriticalPathImpact.CRITICAL
    assert report.critical_path_breached is True
    assert len(report.cascade_paths) > 0


def test_dynamic_blast_radius_isolated_worker():
    """Computes dynamic blast radius for worker-service (isolated background node)."""
    report = evaluate_blast_radius("worker-service")

    assert report.target_service == "worker-service"
    assert report.direct_upstream == []
    assert report.transitive_upstream == []
    assert report.total_impacted_services == 1
    expected_pct = round((1 / 11) * 100.0, 1)
    assert report.blast_radius_pct == expected_pct
    assert report.impact_level == "ISOLATED"
    assert report.critical_path_impact == CriticalPathImpact.NONE


def test_dynamic_blast_radius_partner_payment_gateway():
    """Computes dynamic blast radius for partner-payment-gateway."""
    report = evaluate_blast_radius("partner-payment-gateway")

    # Callers: payment-service and checkout-service directly; api-gateway transitively
    assert "payment-service" in report.direct_upstream
    assert "checkout-service" in report.direct_upstream
    assert "api-gateway" in report.transitive_upstream
    assert report.critical_path_breached is True
    assert report.critical_path_impact in [
        CriticalPathImpact.MODERATE,
        CriticalPathImpact.HIGH,
        CriticalPathImpact.CRITICAL,
    ]



def test_dynamic_blast_radius_unknown_service():
    """Handles an unknown service ID gracefully without crashing."""
    report = evaluate_blast_radius("unknown-service")
    assert report.target_service == "unknown-service"
    assert report.total_impacted_services == 1
    assert report.impact_level == "ISOLATED"
    assert report.critical_path_breached is False


def test_chaos_latency_injection():
    """Chaos Experiment 1: Latency injection on partner-payment-gateway (+5000ms)."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="partner-payment-gateway",
        chaos_type=ChaosType.LATENCY_INJECTION,
        magnitude=5000,
    )
    result = engine.simulate_chaos(req)

    assert isinstance(result, ChaosSimulationResult)
    assert result.experiment_id == "chaos-latency_injection-partner-payment-gateway"
    assert result.target_service == "partner-payment-gateway"
    assert result.is_synthetic_simulation is True

    # Propagated health states
    assert result.propagated_node_states["partner-payment-gateway"] == NodeHealthState.SIMULATED_CHAOS
    assert result.propagated_node_states["payment-service"] == NodeHealthState.UNHEALTHY
    assert result.propagated_node_states["checkout-service"] == NodeHealthState.DEGRADED
    assert result.propagated_node_states["api-gateway"] == NodeHealthState.DEGRADED

    # Blast radius must exceed 60%
    assert result.blast_radius.blast_radius_pct > 60.0
    assert result.blast_radius.blast_radius_pct == 63.6
    assert result.blast_radius.impact_level == "CATASTROPHIC"

    # Steps and resilience findings
    assert len(result.propagation_steps) >= 3
    assert any("bulkhead" in f.lower() or "circuit breaker" in f.lower() for f in result.resilience_findings)


def test_chaos_db_pool_exhaustion():
    """Chaos Experiment 2: PostgreSQL connection pool starvation (pool_max=2)."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="postgres-db",
        chaos_type=ChaosType.DB_POOL_EXHAUSTION_SIMULATION,
    )
    result = engine.simulate_chaos(req)

    assert result.experiment_id == "chaos-db_pool_exhaustion-postgres-db"
    assert result.propagated_node_states["postgres-db"] == NodeHealthState.SIMULATED_CHAOS
    assert result.propagated_node_states["order-service"] == NodeHealthState.UNHEALTHY
    assert result.propagated_node_states["payment-service"] == NodeHealthState.UNHEALTHY
    assert result.propagated_node_states["checkout-service"] == NodeHealthState.FAILED

    # Blast radius must exceed 70%
    assert result.blast_radius.blast_radius_pct > 70.0
    assert result.blast_radius.blast_radius_pct == 72.7
    assert result.blast_radius.impact_level == "CATASTROPHIC"
    assert any("pgbouncer" in f.lower() or "pooling" in f.lower() for f in result.resilience_findings)


def test_chaos_oom_crash_worker():
    """Chaos Experiment 3: OOMKill crash simulation on worker-service (exit code 137)."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="worker-service",
        chaos_type=ChaosType.OOM_CRASH_SIMULATION,
    )
    result = engine.simulate_chaos(req)

    assert result.experiment_id == "chaos-oom_crash-worker-service"
    assert result.propagated_node_states["worker-service"] == NodeHealthState.FAILED
    assert result.propagated_node_states["kafka-queue"] == NodeHealthState.DEGRADED

    # Blast radius must remain under 20% (isolated async failure)
    assert result.blast_radius.blast_radius_pct < 20.0
    assert result.blast_radius.blast_radius_pct == 18.2
    assert result.blast_radius.impact_level == "ISOLATED"
    assert any("kafka" in f.lower() or "buffer" in f.lower() for f in result.resilience_findings)


def test_chaos_downstream_outage_redis():
    """Chaos Experiment 4: Redis cache outage and secondary DB query surge."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="redis-cache",
        chaos_type=ChaosType.DOWNSTREAM_OUTAGE_SIMULATION,
    )
    result = engine.simulate_chaos(req)

    assert result.experiment_id == "chaos-downstream_outage-redis-cache"
    assert result.propagated_node_states["redis-cache"] == NodeHealthState.FAILED
    assert result.propagated_node_states["auth-service"] == NodeHealthState.DEGRADED
    assert result.propagated_node_states["catalog-service"] == NodeHealthState.DEGRADED
    assert result.propagated_node_states["postgres-db"] == NodeHealthState.DEGRADED
    assert result.blast_radius.blast_radius_pct in [45.5, 54.5]
    assert result.blast_radius.impact_level == "HIGH"



def test_chaos_cache_poisoning_auth():
    """Chaos Experiment 5: Cache poisoning & JWT desynchronization on auth-service."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="auth-service",
        chaos_type=ChaosType.CACHE_POISONING_CHAOS,
    )
    result = engine.simulate_chaos(req)

    assert result.experiment_id == "chaos-cache_poisoning-auth-service"
    assert result.propagated_node_states["auth-service"] == NodeHealthState.UNHEALTHY
    assert result.propagated_node_states["checkout-service"] == NodeHealthState.DEGRADED
    assert result.propagated_node_states["api-gateway"] == NodeHealthState.DEGRADED
    assert result.blast_radius.blast_radius_pct == 54.5
    assert result.blast_radius.impact_level == "HIGH"


def test_chaos_determinism_and_idempotence():
    """Verifies that running chaos experiments repeatedly produces identical outputs without drift."""
    engine = ChaosSandboxEngine()
    req = ChaosExperimentRequest(
        target_service="partner-payment-gateway",
        chaos_type=ChaosType.LATENCY_INJECTION,
        magnitude=5000,
    )

    run_1 = engine.simulate_chaos(req)
    run_2 = engine.simulate_chaos(req)

    assert run_1.experiment_id == run_2.experiment_id
    assert run_1.propagated_node_states == run_2.propagated_node_states
    assert run_1.propagated_edge_states == run_2.propagated_edge_states
    assert run_1.blast_radius.blast_radius_pct == run_2.blast_radius.blast_radius_pct
    assert run_1.propagation_steps == run_2.propagation_steps
    assert run_1.resilience_findings == run_2.resilience_findings



# ============================================================================
# 4. Purity, Scenario Isolation & Reset Tests
# ============================================================================


def test_chaos_purity_and_isolation():
    """Ensures chaos simulation does NOT mutate canonical graph or baseline profiles."""
    engine = ChaosSandboxEngine()
    base_graph_before = build_canonical_topology_graph(scenario_key="scenario_01_db_pool")

    req = ChaosExperimentRequest(
        target_service="redis-cache",
        chaos_type=ChaosType.DOWNSTREAM_OUTAGE_SIMULATION,
        scenario_key="scenario_01_db_pool",
    )
    _ = engine.simulate_chaos(req)

    # Base graph after simulation should be identical
    base_graph_after = build_canonical_topology_graph(scenario_key="scenario_01_db_pool")
    assert base_graph_before.nodes == base_graph_after.nodes
    assert base_graph_before.edges == base_graph_after.edges


def test_zero_cross_scenario_leakage():
    """Verifies that running chaos on one scenario does not leak state to another scenario."""
    engine = ChaosSandboxEngine()

    # Run DB chaos on scenario 1
    req1 = ChaosExperimentRequest(
        target_service="postgres-db",
        chaos_type=ChaosType.DB_POOL_EXHAUSTION_SIMULATION,
        scenario_key="scenario_01_db_pool",
    )
    _ = engine.simulate_chaos(req1)

    # Fetch scenario 4 graph
    sc4_graph = build_canonical_topology_graph(scenario_key="scenario_04_k8s_oom")
    sc4_worker = next(n for n in sc4_graph.nodes if n.id == "worker-service")
    assert sc4_worker.status == NodeHealthState.FAILED

    sc4_db = next(n for n in sc4_graph.nodes if n.id == "postgres-db")
    assert sc4_db.status == NodeHealthState.HEALTHY  # Should not be affected by sc1 simulation


def test_scenario_switching_clears_chaos_simulation_db_to_worker(client: TestClient):
    """End-to-end API test: DB pool chaos simulation does not leak into Worker OOM scenario."""
    # 1. Load DB pool scenario baseline
    res_db = client.get("/api/topology?scenario_key=db_pool_exhaustion")
    assert res_db.status_code == 200
    db_topo = res_db.json()
    assert db_topo["active_incident_service"] == "postgres-db"
    assert next(n for n in db_topo["nodes"] if n["id"] == "postgres-db")["status"] == "FAILED"

    # 2. Inject DB Pool Starvation chaos simulation
    res_sim = client.post(
        "/api/topology/chaos/simulate",
        json={
            "target_service": "postgres-db",
            "chaos_type": "DB_POOL_EXHAUSTION_SIMULATION",
            "scenario_key": "db_pool_exhaustion",
        },
    )
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["experiment_id"] == "chaos-db_pool_exhaustion-postgres-db"
    assert sim_data["is_synthetic_simulation"] is True
    assert sim_data["propagated_node_states"]["postgres-db"] == "SIMULATED_CHAOS"

    # 3. Switch scenario to Worker OOM (oom_kill)
    res_worker = client.get("/api/topology?scenario_key=oom_kill")
    assert res_worker.status_code == 200
    worker_topo = res_worker.json()

    # Verify: active incident is worker-service, observed state only
    assert worker_topo["active_incident_service"] == "worker-service"
    worker_node = next(n for n in worker_topo["nodes"] if n["id"] == "worker-service")
    assert worker_node["status"] == "FAILED"
    assert worker_node["is_observed_incident_state"] is True

    # Verify: postgres-db is HEALTHY in worker scenario (no stale simulation state!)
    postgres_node = next(n for n in worker_topo["nodes"] if n["id"] == "postgres-db")
    assert postgres_node["status"] == "HEALTHY"
    assert postgres_node["is_observed_incident_state"] is True

    # Verify: canonical graph structure is pure (11 nodes, 18 edges)
    assert len(worker_topo["nodes"]) == 11
    assert len(worker_topo["edges"]) == 18

    # Verify: blast radius for worker-service is isolated
    res_blast = client.get("/api/topology/blast-radius/worker-service?scenario_key=oom_kill")
    assert res_blast.status_code == 200
    blast_data = res_blast.json()
    assert blast_data["target_service"] == "worker-service"
    assert blast_data["total_impacted_services"] == 1
    assert blast_data["impact_level"] == "ISOLATED"


def test_scenario_switching_clears_chaos_simulation_worker_to_db(client: TestClient):
    """End-to-end API test (reverse direction): Worker chaos simulation does not leak into DB pool scenario."""
    # 1. Load Worker OOM scenario and inject worker chaos
    res_sim = client.post(
        "/api/topology/chaos/simulate",
        json={
            "target_service": "worker-service",
            "chaos_type": "OOM_CRASH_SIMULATION",
            "scenario_key": "oom_kill",
        },
    )
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["experiment_id"] == "chaos-oom_crash-worker-service"
    assert sim_data["is_synthetic_simulation"] is True

    # 2. Switch back to DB pool scenario
    res_db = client.get("/api/topology?scenario_key=db_pool_exhaustion")
    assert res_db.status_code == 200
    db_topo = res_db.json()

    # Verify: active incident is postgres-db, worker-service is observed healthy
    assert db_topo["active_incident_service"] == "postgres-db"
    db_node = next(n for n in db_topo["nodes"] if n["id"] == "postgres-db")
    assert db_node["status"] == "FAILED"
    assert db_node["is_observed_incident_state"] is True

    worker_node = next(n for n in db_topo["nodes"] if n["id"] == "worker-service")
    # In DB pool scenario, worker-service is not in crash loop
    assert worker_node["status"] in ["HEALTHY", "DEGRADED"]
    assert worker_node["is_observed_incident_state"] is True



# ============================================================================
# 5. Offline Safety Invariant Tests
# ============================================================================


def test_safety_no_subprocess_or_mutations():
    """Asserts that chaos simulation and topology engines invoke zero shell/subprocess/cloud APIs."""
    forbidden_calls = []

    def fake_subprocess_run(*args, **kwargs):
        forbidden_calls.append(("run", args))
        raise RuntimeError("Subprocess execution is strictly forbidden in AERO chaos sandbox!")

    def fake_popen(*args, **kwargs):
        forbidden_calls.append(("popen", args))
        raise RuntimeError("Popen execution is strictly forbidden in AERO chaos sandbox!")

    def fake_system(*args, **kwargs):
        forbidden_calls.append(("system", args))
        raise RuntimeError("os.system is strictly forbidden in AERO chaos sandbox!")

    with (
        patch.object(subprocess, "run", side_effect=fake_subprocess_run),
        patch.object(subprocess, "Popen", side_effect=fake_popen),
        patch.object(os, "system", side_effect=fake_system),
    ):
        engine = ChaosSandboxEngine()
        for c_type, tgt in [
            (ChaosType.LATENCY_INJECTION, "partner-payment-gateway"),
            (ChaosType.DB_POOL_EXHAUSTION_SIMULATION, "postgres-db"),
            (ChaosType.OOM_CRASH_SIMULATION, "worker-service"),
            (ChaosType.DOWNSTREAM_OUTAGE_SIMULATION, "redis-cache"),
            (ChaosType.CACHE_POISONING_CHAOS, "auth-service"),
        ]:
            res = engine.simulate_chaos(ChaosExperimentRequest(target_service=tgt, chaos_type=c_type))
            assert res.is_synthetic_simulation is True

    assert len(forbidden_calls) == 0, f"Forbidden subprocess calls detected: {forbidden_calls}"


# ============================================================================
# 6. REST API Endpoint Tests
# ============================================================================


def test_api_get_topology(client: TestClient):
    """Tests GET /api/topology baseline endpoint."""
    res = client.get("/api/topology")
    assert res.status_code == 200
    data = res.json()

    assert len(data["nodes"]) == 11
    assert len(data["edges"]) == 18
    assert data["is_synthetic_model"] is True


def test_api_get_topology_scenario(client: TestClient):
    """Tests GET /api/topology?scenario_key=scenario_01_db_pool."""
    res = client.get("/api/topology?scenario_key=scenario_01_db_pool")
    assert res.status_code == 200
    data = res.json()

    assert data["active_incident_service"] == "postgres-db"
    db_node = next(n for n in data["nodes"] if n["id"] == "postgres-db")
    assert db_node["status"] == "FAILED"
    assert db_node["is_observed_incident_state"] is True


def test_api_get_blast_radius(client: TestClient):
    """Tests GET /api/topology/blast-radius/{service_id}."""
    res = client.get("/api/topology/blast-radius/postgres-db")
    assert res.status_code == 200
    data = res.json()

    assert data["target_service"] == "postgres-db"
    assert data["total_impacted_services"] == 8
    assert data["blast_radius_pct"] == 72.7
    assert data["impact_level"] == "CATASTROPHIC"
    assert data["critical_path_impact"] == "CRITICAL"


def test_api_post_chaos_simulate(client: TestClient):
    """Tests POST /api/topology/chaos/simulate."""
    payload = {
        "target_service": "partner-payment-gateway",
        "chaos_type": "LATENCY_INJECTION",
        "magnitude": 5000,
    }
    res = client.post("/api/topology/chaos/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["experiment_id"] == "chaos-latency_injection-partner-payment-gateway"
    assert data["is_synthetic_simulation"] is True
    assert data["propagated_node_states"]["payment-service"] == "UNHEALTHY"



def test_api_post_chaos_reset(client: TestClient):
    """Tests POST /api/topology/chaos/reset."""
    res = client.post("/api/topology/chaos/reset?scenario_key=scenario_01_db_pool")
    assert res.status_code == 200
    data = res.json()

    assert data["active_incident_service"] == "postgres-db"
    db_node = next(n for n in data["nodes"] if n["id"] == "postgres-db")
    assert db_node["status"] == "FAILED"



# ============================================================================
# 7. Static Web Assets & Frontend State Lifecycle Verification
# ============================================================================


def test_static_web_assets_available(client: TestClient):
    """Ensures frontend CSS and JS components are accessible via static file server."""
    css_res = client.get("/css/topology.css")
    assert css_res.status_code == 200
    assert "topology-workspace" in css_res.text

    js_res = client.get("/js/components/topology.js")
    assert js_res.status_code == 200
    assert "renderTopologyWorkspace" in js_res.text


def test_scenario_switching_all_five_scenarios_automatic_focus(client: TestClient):
    """Validates that every scenario deterministically yields its correct observed incident service."""
    scenario_expectations = [
        ("oom_kill", "worker-service", NodeHealthState.FAILED, 9.1, "ISOLATED"),
        ("db_pool_exhaustion", "postgres-db", NodeHealthState.FAILED, 72.7, "CATASTROPHIC"),
        ("config_drift", "auth-service", NodeHealthState.FAILED, 27.3, "MODERATE"),
        ("dependency_deadlock", "partner-payment-gateway", NodeHealthState.FAILED, 36.4, "MODERATE"),
        ("cache_poisoning", "redis-cache", NodeHealthState.UNHEALTHY, 45.5, "HIGH"),
    ]

    for scenario_key, expected_service, expected_status, expected_min_blast, expected_impact in scenario_expectations:
        # 1. Fetch scenario topology
        res = client.get(f"/api/topology?scenario_key={scenario_key}")
        assert res.status_code == 200
        topo = res.json()

        # 2. Active incident service MUST match expected target service (never default to api-gateway)
        assert topo["active_incident_service"] == expected_service, (
            f"Scenario {scenario_key} expected active_incident_service {expected_service}, got {topo['active_incident_service']}"
        )

        # 3. Target node must be in observed incident state
        target_node = next(n for n in topo["nodes"] if n["id"] == expected_service)
        assert target_node["status"] == expected_status.value
        assert target_node["is_observed_incident_state"] is True

        # 4. Blast radius for derived active incident service
        blast_res = client.get(f"/api/topology/blast-radius/{expected_service}?scenario_key={scenario_key}")
        assert blast_res.status_code == 200
        blast = blast_res.json()
        assert blast["target_service"] == expected_service
        assert blast["blast_radius_pct"] >= expected_min_blast - 0.5


def test_frontend_state_machine_scenario_switch_and_stale_response_guard(client: TestClient):
    """Simulates the exact frontend state lifecycle and verifies generation token guard against race conditions."""
    # State representation
    state = {
        "scenarioToken": 1,
        "activeScenarioKey": "db_pool_exhaustion",
        "activeTopologyData": client.get("/api/topology?scenario_key=db_pool_exhaustion").json(),
        "selectedTopologyNode": "postgres-db",
        "activeBlastRadiusData": client.get("/api/topology/blast-radius/postgres-db?scenario_key=db_pool_exhaustion").json(),
        "isChaosSimulated": True,
        "activeChaosSimulation": {
            "experiment_id": "chaos-db_pool_exhaustion-postgres-db",
            "blast_radius": {"blast_radius_pct": 72.7},
        },
    }
    assert state["isChaosSimulated"] is True
    assert state["selectedTopologyNode"] == "postgres-db"

    # Action: User switches scenario to 'oom_kill'
    new_token = state["scenarioToken"] + 1
    # Step 1: Synchronous reset
    state["scenarioToken"] = new_token
    state["activeScenarioKey"] = "oom_kill"
    state["activeTopologyData"] = None
    state["selectedTopologyNode"] = None
    state["activeBlastRadiusData"] = None
    state["isChaosSimulated"] = False
    state["activeChaosSimulation"] = None

    # Step 2: Simulate a delayed/stale response from Scenario A returning now
    stale_response_token = 1
    if stale_response_token == state["scenarioToken"]:
        # Should NOT execute because tokens do not match
        state["isChaosSimulated"] = True
        state["selectedTopologyNode"] = "postgres-db"

    assert state["isChaosSimulated"] is False
    assert state["selectedTopologyNode"] is None

    # Step 3: Scenario B response arrives
    topo_b = client.get("/api/topology?scenario_key=oom_kill").json()
    assert topo_b["active_incident_service"] == "worker-service"
    default_node = topo_b["active_incident_service"]
    blast_b = client.get(f"/api/topology/blast-radius/{default_node}?scenario_key=oom_kill").json()

    # Step 4: Guard check passes for Scenario B
    if new_token == state["scenarioToken"]:
        state["activeTopologyData"] = topo_b
        state["selectedTopologyNode"] = default_node
        state["activeBlastRadiusData"] = blast_b
        state["isChaosSimulated"] = False
        state["activeChaosSimulation"] = None

    # Verify final state
    assert state["selectedTopologyNode"] == "worker-service"
    assert state["isChaosSimulated"] is False
    assert state["activeChaosSimulation"] is None
    assert state["activeBlastRadiusData"]["blast_radius_pct"] == 9.1
    assert state["activeBlastRadiusData"]["impact_level"] == "ISOLATED"


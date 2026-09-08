"""Tests for AERO Phase 4 Stage 4G: Pre-Deployment Risk Advisor."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.service import AeroService
from src.risk.engine import DeterministicRiskEngine
from src.schemas.risk import (
    ProposedChange,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)

client = TestClient(app)


def test_risk_schemas_validation():
    """Verify Pydantic models for ProposedChange, RiskFinding, and RiskAnalysisResponse."""
    change = ProposedChange(
        service="worker-service",
        change_type="deployment",
        description="Update worker pool limits",
        parameters={"memory_limit_mb": 2048, "memory_request_mb": 1024},
        environment="production",
        rollback_plan="Revert to v2.4.0",
    )
    assert change.service == "worker-service"
    assert change.parameters["memory_limit_mb"] == 2048

    finding = RiskFinding(
        rule_id="RISK-RES-001",
        title="Resource Constraint Risk",
        severity=RiskSeverity.HIGH,
        category=RiskCategory.RESOURCE_LIMITS,
        observed_facts=["Memory limit set to 2048MB"],
        derived_risk="Potential memory pressure",
        recommendations=["Increase to 4096MB"],
        score_impact=20,
    )
    assert finding.rule_id == "RISK-RES-001"
    assert finding.severity == RiskSeverity.HIGH

    req = RiskAnalysisRequest(proposed_change=change, scenario_key="oom_kill")
    assert req.scenario_key == "oom_kill"
    assert req.provider == "deterministic"

    resp = RiskAnalysisResponse(
        overall_severity=RiskSeverity.HIGH,
        risk_score=65,
        is_safe_to_deploy=False,
        findings=[finding],
        observed_facts_summary=["Memory limit set to 2048MB"],
        preventive_recommendations=["Increase to 4096MB"],
        rule_evaluation_count=8,
        scenario_context_applied=True,
    )
    assert resp.is_safe_to_deploy is False
    assert resp.risk_score == 65


def test_risk_rule_resource_request_exceeds_limit():
    """Verify RISK-RES-001 triggers CRITICAL when memory request > limit."""
    change = ProposedChange(
        service="worker-service",
        change_type="deployment",
        description="Invalid pod spec where request exceeds limit",
        parameters={"memory_request_mb": 4096, "memory_limit_mb": 1024},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert resp.overall_severity == RiskSeverity.CRITICAL
    assert resp.is_safe_to_deploy is False
    assert any(f.rule_id == "RISK-RES-001" for f in resp.findings)
    assert any("exceeds memory limit" in fact for fact in resp.observed_facts_summary)


def test_risk_rule_missing_resource_limits_prod():
    """Verify RISK-RES-002 triggers HIGH when production deployment has no memory limit."""
    change = ProposedChange(
        service="order-service",
        change_type="deployment",
        description="Deploy order service without resource boundaries",
        parameters={},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert any(f.rule_id == "RISK-RES-002" for f in resp.findings)
    assert resp.is_safe_to_deploy is False or resp.overall_severity in [RiskSeverity.HIGH, RiskSeverity.CRITICAL]


def test_risk_rule_resource_regression_below_incident_telemetry_peak():
    """Verify RISK-RES-003 flags proposed limit below active incident telemetry peak."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    incident = bundle.incident

    # Proposed change has 512MB limit, while oom_kill telemetry has ~1.95 GB peak
    change = ProposedChange(
        service="worker-service",
        change_type="resource",
        description="Downscale worker memory to 512MB",
        parameters={"memory_limit_mb": 512, "memory_request_mb": 256},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change, incident=incident)

    assert any(f.rule_id == "RISK-RES-003" for f in resp.findings)
    assert resp.overall_severity == RiskSeverity.CRITICAL
    assert resp.is_safe_to_deploy is False
    assert resp.scenario_context_applied is True


def test_risk_rule_database_pool_starvation():
    """Verify RISK-POOL-001 flags severely undersized DB connection pool (<5)."""
    change = ProposedChange(
        service="order-service",
        change_type="config",
        description="Constrain DB connection pool to 2 connections",
        parameters={"pool_max_size": 2},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert any(f.rule_id == "RISK-POOL-001" for f in resp.findings)
    assert resp.overall_severity == RiskSeverity.CRITICAL
    assert resp.is_safe_to_deploy is False


def test_risk_rule_timeout_cascade_and_infinite_timeout():
    """Verify RISK-TIMEOUT-001 and RISK-TIMEOUT-003 for infinite or mismatched timeouts."""
    # 1. Infinite timeout (0)
    change_inf = ProposedChange(
        service="checkout-service",
        change_type="config",
        description="Disable RPC timeout",
        parameters={"timeout_ms": 0},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp_inf = engine.evaluate(change_inf)
    assert any(f.rule_id == "RISK-TIMEOUT-001" for f in resp_inf.findings)

    # 2. Downstream > Upstream timeout
    change_mismatch = ProposedChange(
        service="checkout-service",
        change_type="config",
        description="Extend downstream timeout",
        parameters={"downstream_timeout_ms": 30000, "upstream_timeout_ms": 5000},
        environment="production",
    )
    resp_mismatch = engine.evaluate(change_mismatch)
    assert any(f.rule_id == "RISK-TIMEOUT-003" for f in resp_mismatch.findings)


def test_risk_rule_missing_readiness_probe():
    """Verify RISK-PROBE-001 triggers when readiness probe is explicitly disabled."""
    change = ProposedChange(
        service="payment-service",
        change_type="deployment",
        description="Deploy without readiness checks",
        parameters={"readiness_probe_enabled": False},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert any(f.rule_id == "RISK-PROBE-001" for f in resp.findings)
    assert any("readiness probe" in f.title.lower() for f in resp.findings)



def test_risk_rule_dangerous_config_debug_in_prod():
    """Verify RISK-CONFIG-001 flags debug_mode in production environment."""
    change = ProposedChange(
        service="auth-service",
        change_type="config",
        description="Enable debug logging in prod for troubleshooting",
        parameters={"debug_mode": True, "log_level": "DEBUG"},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert any(f.rule_id == "RISK-CONFIG-001" for f in resp.findings)
    assert resp.overall_severity in [RiskSeverity.HIGH, RiskSeverity.CRITICAL]


def test_risk_rule_config_drift_detection():
    """Verify RISK-DRIFT-001 flags active configuration drift."""
    bundle = AeroService.get_scenario_bundle("config_drift", seed=42)
    change = ProposedChange(
        service="order-service",
        change_type="config",
        description="Update pool config while drift is active",
        parameters={"config_drift_detected": True},
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change, incident=bundle.incident)

    assert any(f.rule_id == "RISK-DRIFT-001" for f in resp.findings)


def test_risk_rule_tier1_service_blast_radius():
    """Verify RISK-SERVICE-001 flags changes to revenue-critical services."""
    change = ProposedChange(
        service="checkout-service",
        change_type="deployment",
        description="Routine patch to checkout-service",
        parameters={
            "memory_limit_mb": 2048,
            "memory_request_mb": 1024,
            "readiness_probe_enabled": True,
            "pool_max_size": 25,
            "rollback_version": "v2.4.0",
        },
        environment="production",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert any(f.rule_id == "RISK-SERVICE-001" for f in resp.findings)
    # With safe params, overall severity should be LOW or MEDIUM and safe to deploy
    assert resp.is_safe_to_deploy is True
    assert resp.overall_severity == RiskSeverity.LOW or resp.overall_severity == RiskSeverity.MEDIUM


def test_risk_insufficient_input_handling():
    """Verify Risk Advisor handles sparse input gracefully without hallucinating."""
    change = ProposedChange(
        service="custom-service",
        change_type="config",
        description="Fix",
        parameters={},
        environment="staging",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert resp.insufficient_data is True
    assert any(f.rule_id == "RISK-INSUFFICIENT-001" for f in resp.findings)
    assert "Sparse change input" in resp.explanation or "heuristic" in resp.explanation.lower()


def test_risk_score_aggregation_and_safe_canary():
    """Verify fully compliant change produces low risk score and is safe to deploy."""
    change = ProposedChange(
        service="payment-service",
        change_type="deployment",
        description="Canary deployment of v2.4.2 with verified limits and rollback target",
        parameters={
            "image_tag": "v2.4.2",
            "memory_limit_mb": 2048,
            "memory_request_mb": 1024,
            "cpu_limit_cores": 2.0,
            "cpu_request_cores": 1.0,
            "pool_max_size": 25,
            "timeout_ms": 3000,
            "readiness_probe_enabled": True,
            "liveness_initial_delay_seconds": 15,
            "rollback_version": "v2.4.1",
        },
        environment="production",
        rollback_plan="Rollback to v2.4.1 if p99 latency exceeds 300ms",
    )
    engine = DeterministicRiskEngine()
    resp = engine.evaluate(change)

    assert resp.risk_score <= 25
    assert resp.is_safe_to_deploy is True
    assert resp.overall_severity in [RiskSeverity.LOW, RiskSeverity.MEDIUM]
    assert len(resp.preventive_recommendations) > 0


def test_api_risk_analyze_success():
    """Verify POST /api/risk/analyze endpoint returns HTTP 200 with structured response."""
    payload = {
        "proposed_change": {
            "service": "order-service",
            "change_type": "deployment",
            "description": "Deploy order-service v2.5.0 with low memory limit",
            "parameters": {
                "memory_limit_mb": 256,
                "memory_request_mb": 128,
                "pool_max_size": 2,
            },
            "environment": "production",
        },
        "scenario_key": "db_pool_exhaustion",
        "provider": "deterministic",
    }
    res = client.post("/api/risk/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["overall_severity"] in ["HIGH", "CRITICAL"]
    assert data["risk_score"] > 40
    assert data["is_safe_to_deploy"] is False
    assert len(data["findings"]) >= 1
    assert len(data["observed_facts_summary"]) >= 1
    assert len(data["preventive_recommendations"]) >= 1
    assert data["scenario_context_applied"] is True


def test_api_risk_analyze_empty_service_400():
    """Verify POST /api/risk/analyze rejects empty service name with HTTP 400."""
    payload = {
        "proposed_change": {
            "service": "   ",
            "change_type": "deployment",
            "description": "Empty service test",
            "parameters": {},
        }
    }
    res = client.post("/api/risk/analyze", json=payload)
    assert res.status_code == 400
    assert "service" in res.json()["detail"].lower()


def test_api_risk_analyze_empty_description_400():
    """Verify POST /api/risk/analyze rejects empty description with HTTP 400."""
    payload = {
        "proposed_change": {
            "service": "order-service",
            "change_type": "deployment",
            "description": "   ",
            "parameters": {},
        }
    }
    res = client.post("/api/risk/analyze", json=payload)
    assert res.status_code == 400
    assert "description" in res.json()["detail"].lower()


def test_api_risk_analyze_unknown_scenario_404():
    """Verify POST /api/risk/analyze returns HTTP 404 for unknown scenario_key."""
    payload = {
        "proposed_change": {
            "service": "order-service",
            "change_type": "deployment",
            "description": "Unknown scenario test",
            "parameters": {},
        },
        "scenario_key": "nonexistent_scenario_key",
    }
    res = client.post("/api/risk/analyze", json=payload)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_risk_advisor_scenario_switching_isolation():
    """Verify Risk Advisor evaluations across scenarios are strictly isolated."""
    # Scenario A: oom_kill context
    req_a = {
        "proposed_change": {
            "service": "worker-service",
            "change_type": "resource",
            "description": "Memory adjustment",
            "parameters": {"memory_limit_mb": 512},
            "environment": "production",
        },
        "scenario_key": "oom_kill",
    }
    res_a = client.post("/api/risk/analyze", json=req_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert any("worker-service" in str(f) for f in data_a["findings"])
    assert any("telemetry" in str(f).lower() for f in data_a["findings"])

    # Scenario B: cache_poisoning context
    req_b = {
        "proposed_change": {
            "service": "auth-service",
            "change_type": "config",
            "description": "Auth token cache config",
            "parameters": {"pool_max_size": 25},
            "environment": "production",
        },
        "scenario_key": "cache_poisoning",
    }
    res_b = client.post("/api/risk/analyze", json=req_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    # Confirm no worker-service leakage into auth-service analysis
    assert "worker-service" not in str(data_b)


def test_risk_advisor_static_assets_serve():
    """Verify Risk Advisor CSS and JS component modules serve cleanly via FastAPI."""
    res_css = client.get("/css/risk_advisor.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".risk-drawer" in res_css.text
    assert ".risk-facts-block" in res_css.text
    assert ".risk-findings-block" in res_css.text
    assert ".risk-recs-block" in res_css.text
    assert ".risk-resize-handle" in res_css.text

    res_js = client.get("/js/components/risk_advisor.js")
    assert res_js.status_code == 200
    assert "application/javascript" in res_js.headers.get("content-type", "")
    assert "initRiskAdvisorDrawer" in res_js.text
    assert "toggleRiskAdvisorDrawer" in res_js.text
    assert "resetRiskAdvisor" in res_js.text


def test_risk_advisor_safety_invariants_no_subprocess_or_mutation(monkeypatch):
    """Verify Risk Advisor execution NEVER invokes subprocesses or mutates infrastructure."""
    import subprocess

    def forbidden_call(*args, **kwargs):
        raise AssertionError("Risk Advisor attempted to invoke subprocess or shell command!")

    monkeypatch.setattr(subprocess, "run", forbidden_call)
    monkeypatch.setattr(subprocess, "Popen", forbidden_call)

    payload = {
        "proposed_change": {
            "service": "order-service",
            "change_type": "deployment",
            "description": "Safety invariant test change",
            "parameters": {"memory_limit_mb": 1024},
            "environment": "production",
        },
        "scenario_key": "oom_kill",
    }
    res = client.post("/api/risk/analyze", json=payload)
    assert res.status_code == 200
    assert res.json()["rule_evaluation_count"] > 0

"""Unit tests for the AERO FastAPI Gateway endpoints."""

import json

from fastapi.testclient import TestClient

from src.api.app import app
from src.benchmark.scenarios.oom_kill import generate_oom_kill_scenario

client = TestClient(app)


def test_healthz_endpoint():
    """Verifies that /healthz returns 200 with service health and GCP project metadata."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "gcp_project_id" in data
    assert "gcp_region" in data


def test_config_endpoint():
    """Verifies that /api/config returns active model configuration."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "reasoning_model" in data
    assert "diagnostic_provider" in data


def test_list_scenarios_endpoint():
    """Verifies that /api/scenarios returns all 5 benchmark scenarios."""
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 5
    ids = [s["scenario_id"] for s in scenarios]
    assert "oom_kill" in ids
    assert "db_pool_exhaustion" in ids


def test_get_scenario_bundle_endpoint():
    """Verifies that /api/scenarios/{key} returns full scenario bundle with telemetry."""
    response = client.get("/api/scenarios/oom_kill")
    assert response.status_code == 200
    bundle = response.json()
    assert "ground_truth" in bundle
    assert "incident" in bundle
    assert bundle["ground_truth"]["affected_service"] == "worker-service"

    # Non-existent scenario
    err_resp = client.get("/api/scenarios/nonexistent_scenario")
    assert err_resp.status_code == 404


def test_diagnose_endpoint():
    """Verifies that POST /api/diagnose runs diagnostic engine with grounding verification."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident_dict = json.loads(bundle.incident.model_dump_json())

    response = client.post(
        "/api/diagnose",
        json={"incident": incident_dict, "provider": "mock"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert "grounding" in data
    assert data["report"]["probable_root_cause"]["category"] == "RESOURCE_EXHAUSTION_MEMORY"
    assert data["grounding"]["is_fully_grounded"] is True


def test_timeline_endpoint():
    """Verifies that POST /api/timeline synthesizes chronological milestones."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident_dict = json.loads(bundle.incident.model_dump_json())

    response = client.post(
        "/api/timeline",
        json={"incident": incident_dict},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == bundle.incident.metadata.incident_id
    assert len(data["milestones"]) >= 5


def test_replay_endpoint():
    """Verifies that POST /api/timeline/replay generates step-by-step state snapshots."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident_dict = json.loads(bundle.incident.model_dump_json())

    response = client.post(
        "/api/timeline/replay",
        json={"incident": incident_dict, "interval_seconds": 60},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "worker-service"
    assert data["total_steps"] > 0
    assert len(data["snapshots"]) == data["total_steps"]


def test_postmortem_endpoint():
    """Verifies that POST /api/postmortem authors structured postmortem and markdown report."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident_dict = json.loads(bundle.incident.model_dump_json())

    response = client.post(
        "/api/postmortem",
        json={"incident": incident_dict, "provider": "mock"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "postmortem" in data
    assert "markdown" in data
    assert "## 1. Executive Summary" in data["markdown"]
    assert data["postmortem"]["root_cause"]["category"] == "RESOURCE_EXHAUSTION_MEMORY"


def test_evaluate_endpoint():
    """Verifies that POST /api/evaluate executes the benchmark evaluation suite."""
    response = client.post(
        "/api/evaluate",
        json={"scenario_keys": ["oom_kill"], "provider": "mock", "seed": 42},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["total_scenarios"] == 1
    assert report["passed_scenarios"] == 1
    assert report["all_passed"] is True

"""Tests for Stage 4A: Product Shell and Static UI Delivery."""

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_web_shell_root_serves_html():
    """Verify GET / returns 200 and serves index.html with AERO branding."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text

    # Core Branding & Title
    assert "AERO" in content
    assert "AI-Enabled Reliability and Operations" in content
    
    # Header & Control elements
    assert 'id="scenario-select"' in content
    assert 'id="gcp-badge"' in content
    assert 'id="gcp-project-id"' in content
    assert 'id="btn-provider-mock"' in content
    assert 'id="btn-provider-live"' in content
    
    # Lifecycle Navigation
    assert 'id="lifecycle-nav"' in content
    assert 'data-tab="telemetry"' in content
    assert 'data-tab="timeline"' in content
    assert 'data-tab="rca"' in content
    assert 'data-tab="grounding"' in content
    assert 'data-tab="remediation"' in content
    assert 'data-tab="postmortem"' in content
    assert 'data-tab="architecture"' in content

    # Workspaces & script references
    assert 'id="main-workspace"' in content
    assert 'id="left-pane"' in content
    assert 'id="right-pane"' in content
    assert '<script type="module" src="js/app.js">' in content


def test_web_shell_css_assets_serve():
    """Verify all Stage 4A CSS stylesheets are served successfully."""
    for css_file in ["design_system.css", "layout.css", "components.css"]:
        res = client.get(f"/css/{css_file}")
        assert res.status_code == 200, f"Failed to load /css/{css_file}"
        assert "text/css" in res.headers.get("content-type", "")
        assert len(res.text) > 50


def test_web_shell_js_assets_serve():
    """Verify all Stage 4A JavaScript modules are served successfully."""
    for js_file in ["app.js", "state.js", "api.js", "components/header.js"]:
        res = client.get(f"/js/{js_file}")
        assert res.status_code == 200, f"Failed to load /js/{js_file}"
        assert len(res.text) > 50


def test_web_shell_backend_api_integration():
    """Verify REST API contracts used by the UI shell respond cleanly."""
    # Health check
    health_res = client.get("/healthz")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "HEALTHY"
    assert "gcp_project_id" in health_res.json()

    # Config
    cfg_res = client.get("/api/config")
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert "project_id" in cfg_data
    assert "reasoning_model" in cfg_data
    assert "diagnostic_provider" in cfg_data

    # Scenarios list
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()
    assert len(scenarios) == 5
    scenario_keys = [s["scenario_id"] for s in scenarios]
    assert "db_pool_exhaustion" in scenario_keys
    assert "oom_kill" in scenario_keys

    # Scenario detail
    detail_res = client.get("/api/scenarios/db_pool_exhaustion")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "incident" in detail
    assert "ground_truth" in detail
    assert detail["ground_truth"]["affected_service"] == "checkout-service" or "service" in detail["ground_truth"]["affected_service"]


def test_web_shell_all_scenarios_have_valid_telemetry_counts():
    """Verify all 5 benchmark scenarios provide complete metadata and positive telemetry counts for UI shell."""
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()
    assert len(scenarios) == 5

    for sc in scenarios:
        scenario_key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{scenario_key}")
        assert res.status_code == 200, f"Failed to fetch scenario {scenario_key}"
        bundle = res.json()

        # Metadata assertions
        assert "incident" in bundle
        assert "ground_truth" in bundle
        incident = bundle["incident"]
        metadata = incident["metadata"]
        telemetry = incident["telemetry"]

        # Ensure title, service, and incident ID are non-empty
        assert metadata["title"], f"Empty title in scenario {scenario_key}"
        assert metadata["affected_service"], f"Empty affected_service in scenario {scenario_key}"
        assert metadata["incident_id"], f"Empty incident_id in scenario {scenario_key}"
        assert metadata["severity"], f"Empty severity in scenario {scenario_key}"

        # Ensure non-zero telemetry counts for logs & metrics
        assert len(telemetry["logs"]) > 50, f"Expected >50 logs in {scenario_key}, got {len(telemetry['logs'])}"
        assert len(telemetry["metrics"]) > 0, f"Expected >0 metrics in {scenario_key}, got {len(telemetry['metrics'])}"
        assert len(telemetry["health_signals"]) > 0, f"Expected >0 health signals in {scenario_key}"


"""Tests for Stage 4B: Incident Workspace & Telemetry UI Delivery."""

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_stage4b_telemetry_static_assets_serve():
    """Verify all Stage 4B CSS and JS component modules are served cleanly."""
    # CSS
    res_css = client.get("/css/telemetry.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".telemetry-workspace" in res_css.text
    assert ".metrics-grid" in res_css.text

    # JS Components
    components = [
        "telemetry.js",
        "metrics_chart.js",
        "log_explorer.js",
        "deployments.js",
        "health_monitor.js"
    ]
    for comp in components:
        res_js = client.get(f"/js/components/{comp}")
        assert res_js.status_code == 200, f"Failed to load /js/components/{comp}"
        assert "application/javascript" in res_js.headers.get("content-type", "")
        assert len(res_js.text) > 50


def test_stage4b_golden_signals_metrics_all_scenarios():
    """Verify all 5 benchmark scenarios supply golden signal metric time series for chart rendering."""
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()
    assert len(scenarios) == 5

    expected_metrics = {
        "oom_kill": ["container/memory_utilization", "http/server/error_rate"],
        "db_pool_exhaustion": ["database/pool/active_connections", "http/server/error_rate"],
        "config_drift": ["auth/jwt_verification_failure_rate", "http/server/error_rate"],
        "dependency_deadlock": ["dependency/partner_payment_latency_p99", "server/active_worker_threads", "container/cpu_utilization"],
        "cache_poisoning": ["redis/cache_hit_ratio", "database/cpu_utilization"]
    }

    for sc in scenarios:
        key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{key}")
        assert res.status_code == 200
        bundle = res.json()

        metrics = bundle["incident"]["telemetry"]["metrics"]
        assert len(metrics) >= 2, f"Expected >=2 metric series in {key}"

        metric_names = [m["metric_name"] for m in metrics]
        for expected in expected_metrics[key]:
            assert expected in metric_names, f"Expected {expected} in {key} metrics"

        # Validate points structure in each metric
        for m in metrics:
            assert len(m["points"]) >= 10, f"Metric {m['metric_name']} has insufficient points ({len(m['points'])})"
            for pt in m["points"]:
                assert "timestamp" in pt
                assert isinstance(pt["value"], (int, float))


def test_stage4b_log_evidence_filtering_and_highlighting():
    """Verify log records and presence of FATAL/ERROR incident evidence across scenarios."""
    scenarios_res = client.get("/api/scenarios")
    scenarios = scenarios_res.json()

    for sc in scenarios:
        key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{key}")
        bundle = res.json()

        logs = bundle["incident"]["telemetry"]["logs"]
        assert len(logs) >= 200, f"Expected >=200 logs in {key}, got {len(logs)}"

        # Must have at least one critical/fatal or error evidence log
        error_logs = [l for l in logs if l["log_level"] in ("FATAL", "ERROR")]
        assert len(error_logs) >= 1, f"Expected at least 1 FATAL/ERROR log in scenario {key}"

        for log in logs:
            assert log["timestamp"], "Missing timestamp in log"
            assert log["service_name"], "Missing service_name in log"
            assert log["log_level"] in ("DEBUG", "INFO", "WARN", "ERROR", "FATAL")
            assert log["message"], "Missing message in log"


def test_stage4b_deployment_evidence_and_zero_deploy_handling():
    """Verify deployment events and explicit zero-deployment handling for deadlock scenario."""
    # Scenario with 1 deployment
    res_oom = client.get("/api/scenarios/oom_kill")
    bundle_oom = res_oom.json()
    deps_oom = bundle_oom["incident"]["telemetry"]["deployments"]
    assert len(deps_oom) == 1
    assert deps_oom[0]["version"]
    assert deps_oom[0]["commit_hash"]
    assert deps_oom[0]["change_summary"]

    # Scenario with 0 deployments (dependency_deadlock)
    res_deadlock = client.get("/api/scenarios/dependency_deadlock")
    bundle_deadlock = res_deadlock.json()
    deps_deadlock = bundle_deadlock["incident"]["telemetry"]["deployments"]
    assert len(deps_deadlock) == 0


def test_stage4b_service_health_monitor_signals():
    """Verify service health signals and unhealthy probe status during incidents."""
    scenarios_res = client.get("/api/scenarios")
    scenarios = scenarios_res.json()

    for sc in scenarios:
        key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{key}")
        bundle = res.json()

        health = bundle["incident"]["telemetry"]["health_signals"]
        assert len(health) >= 50, f"Expected >=50 health signals in {key}"

        unhealthy = [h for h in health if h["status"] == "UNHEALTHY"]
        assert len(unhealthy) >= 5, f"Expected at least 5 UNHEALTHY probes during incident in {key}"

        for h in health:
            assert h["status"] in ("HEALTHY", "DEGRADED", "UNHEALTHY")
            assert isinstance(h["latency_p99_ms"], (int, float))
            assert isinstance(h["error_rate_pct"], (int, float))

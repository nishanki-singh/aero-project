"""Tests for Stage 4C: Incident Timeline & State Machine Replay UI Delivery."""

from datetime import datetime

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_stage4c_timeline_static_assets_serve():
    """Verify all Stage 4C CSS and JS component modules are served cleanly."""
    # CSS
    res_css = client.get("/css/timeline.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".timeline-workspace" in res_css.text
    assert ".timeline-track-container" in res_css.text
    assert ".replay-slider" in res_css.text
    assert ".snapshot-card" in res_css.text

    # JS Components
    components = [
        "timeline.js",
        "timeline_event.js",
        "snapshot_panel.js",
        "replay_controls.js",
    ]
    for comp in components:
        res_js = client.get(f"/js/components/{comp}")
        assert res_js.status_code == 200, f"Failed to load /js/components/{comp}"
        assert "application/javascript" in res_js.headers.get("content-type", "")
        assert len(res_js.text) > 50


def test_stage4c_scenario_timeline_endpoint_all_scenarios():
    """Verify GET /api/scenarios/{key}/timeline returns sorted milestones for all benchmark scenarios."""
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()
    assert len(scenarios) == 5

    valid_types = {
        "ANOMALY_ONSET",
        "ALERT_FIRED",
        "TRIAGE_START",
        "PEAK_IMPACT",
        "MITIGATION_APPLIED",
        "RECOVERY_VERIFIED",
        "RESOLVED",
    }
    valid_signals = {"LOG", "METRIC", "DEPLOYMENT", "HEALTH", "ALERT", "OPERATOR"}

    for sc in scenarios:
        key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{key}/timeline")
        assert res.status_code == 200, f"Failed to fetch timeline for {key}"
        data = res.json()

        assert data["incident_id"]
        assert data["service_name"]
        assert data["total_duration_minutes"] > 0
        assert data["time_to_detect_minutes"] is not None
        assert data["time_to_mitigate_minutes"] is not None

        milestones = data["milestones"]
        assert len(milestones) >= 4, f"Scenario {key} has too few milestones ({len(milestones)})"

        # Verify chronological ordering
        timestamps = [datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) for m in milestones]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1], f"Milestones out of order in {key}"

        # Verify fields and types
        for m in milestones:
            assert m["timestamp"]
            assert m["milestone_type"] in valid_types, f"Invalid milestone_type {m['milestone_type']} in {key}"
            assert m["source_signal"] in valid_signals, f"Invalid source_signal {m['source_signal']} in {key}"
            assert m["title"]
            assert m["description"]
            assert m["source_service"]


def test_stage4c_scenario_replay_endpoint_all_scenarios():
    """Verify GET /api/scenarios/{key}/replay returns ordered state snapshots with metrics and logs."""
    scenarios_res = client.get("/api/scenarios")
    assert scenarios_res.status_code == 200
    scenarios = scenarios_res.json()

    for sc in scenarios:
        key = sc["scenario_id"]
        res = client.get(f"/api/scenarios/{key}/replay?interval_seconds=60")
        assert res.status_code == 200, f"Failed to fetch replay for {key}"
        data = res.json()

        assert data["incident_id"]
        assert data["service_name"]
        assert data["interval_seconds"] == 60
        assert data["total_steps"] > 0

        snapshots = data["snapshots"]
        assert len(snapshots) == data["total_steps"]
        assert len(snapshots) >= 20, f"Scenario {key} has too few snapshots ({len(snapshots)})"

        for idx, snap in enumerate(snapshots):
            assert snap["step_index"] == idx, f"Snapshot step_index mismatch at {idx} in {key}"
            assert snap["timestamp"]
            assert snap["service_name"]
            assert snap["health_status"] in ("HEALTHY", "DEGRADED", "CRITICAL", "UNHEALTHY", "RECOVERING")
            assert 0.0 <= snap["error_rate_pct"] <= 100.0
            assert snap["latency_p99_ms"] >= 0.0
            assert snap["active_error_count"] >= 0

            # If errors present, sample error log should be populated
            if snap["active_error_count"] > 0:
                assert snap["sample_error_log"] is not None


def test_stage4c_zero_deployment_scenario_handling():
    """Verify timeline & replay behavior for zero-deployment scenario (dependency_deadlock)."""
    # 1. Timeline for dependency_deadlock should have 0 DEPLOYMENT signals
    res_tl = client.get("/api/scenarios/dependency_deadlock/timeline")
    assert res_tl.status_code == 200
    tl = res_tl.json()

    dep_milestones = [m for m in tl["milestones"] if m["source_signal"] == "DEPLOYMENT"]
    assert len(dep_milestones) == 0, "Expected zero deployment milestones in dependency_deadlock"

    # Must still contain anomaly, alert, triage, peak impact, mitigation, and recovery
    types_present = {m["milestone_type"] for m in tl["milestones"]}
    assert "ALERT_FIRED" in types_present
    assert "TRIAGE_START" in types_present
    assert "RECOVERY_VERIFIED" in types_present

    # 2. Timeline for oom_kill should have 1 DEPLOYMENT signal
    res_oom = client.get("/api/scenarios/oom_kill/timeline")
    assert res_oom.status_code == 200
    tl_oom = res_oom.json()

    dep_oom = [m for m in tl_oom["milestones"] if m["source_signal"] == "DEPLOYMENT"]
    assert len(dep_oom) == 1
    assert "v1.9.0" in dep_oom[0]["title"] or "payment-service" in dep_oom[0]["title"]


def test_stage4c_direct_post_timeline_and_replay_endpoints():
    """Verify POST /api/timeline and POST /api/timeline/replay directly synthesize incident data."""
    # Get an incident bundle to use as payload
    sc_res = client.get("/api/scenarios/oom_kill")
    incident_dict = sc_res.json()["incident"]

    # 1. POST /api/timeline
    tl_res = client.post("/api/timeline", json={"incident": incident_dict})
    assert tl_res.status_code == 200
    tl_data = tl_res.json()
    assert tl_data["incident_id"] == incident_dict["metadata"]["incident_id"]
    assert len(tl_data["milestones"]) >= 5

    # 2. POST /api/timeline/replay
    replay_res = client.post("/api/timeline/replay", json={"incident": incident_dict, "interval_seconds": 120})
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    assert replay_data["interval_seconds"] == 120
    assert replay_data["total_steps"] > 0
    assert len(replay_data["snapshots"]) == replay_data["total_steps"]


def test_stage4c_nonexistent_scenario_404():
    """Verify 404 is returned for non-existent scenario keys."""
    res_tl = client.get("/api/scenarios/non_existent_key/timeline")
    assert res_tl.status_code == 404

    res_rp = client.get("/api/scenarios/non_existent_key/replay")
    assert res_rp.status_code == 404


def test_stage4c_replay_point_in_time_consistency_oom_kill():
    """Verify replay snapshots at T+24 and T+25 reflect recovery and resolution."""
    res = client.get("/api/scenarios/oom_kill/replay?interval_seconds=60")
    assert res.status_code == 200
    data = res.json()
    snapshots = data["snapshots"]

    # Step 24 (T+24m - 14:24)
    snap_24 = snapshots[24]
    assert snap_24["step_index"] == 24
    assert snap_24["health_status"] == "HEALTHY"
    assert snap_24["error_rate_pct"] == 0.0
    assert snap_24["latency_p99_ms"] == 25.0
    assert snap_24["active_error_count"] == 0
    assert "Recovery Verified" in snap_24["active_annotation"]

    # Step 25 (T+25m - 14:25)
    snap_25 = snapshots[25]
    assert snap_25["step_index"] == 25
    assert snap_25["health_status"] == "HEALTHY"
    assert snap_25["error_rate_pct"] == 0.0
    assert snap_25["latency_p99_ms"] == 25.0
    assert snap_25["active_error_count"] == 0
    assert "Incident Formally Resolved" in snap_25["active_annotation"]

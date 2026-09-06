"""Tests for Stage 4E: SRE Postmortem Studio & Export."""

from fastapi.testclient import TestClient

from src.api.app import app
from src.schemas.postmortem import AeroPostmortem

client = TestClient(app)


def test_stage4e_postmortem_static_assets_serve():
    """Verify all Stage 4E CSS and JS component modules are served cleanly."""
    # CSS
    res_css = client.get("/css/postmortem.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".postmortem-workspace" in res_css.text
    assert ".postmortem-doc-card" in res_css.text
    assert ".postmortem-meta-grid" in res_css.text
    assert ".pm-action-table" in res_css.text
    assert ".pm-lessons-grid" in res_css.text

    # JS Component
    res_js = client.get("/js/components/postmortem.js")
    assert res_js.status_code == 200
    assert "application/javascript" in res_js.headers.get("content-type", "")
    assert len(res_js.text) > 100
    assert "renderPostmortemStudio" in res_js.text


def test_stage4e_scenario_postmortem_endpoint_all_scenarios():
    """Verify postmortem endpoints return structured postmortem and markdown for all 5 scenarios."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

    expected_services = {
        "oom_kill": "worker-service",
        "db_pool_exhaustion": "order-service",
        "config_drift": "auth-service",
        "dependency_deadlock": "checkout-service",
        "cache_poisoning": "catalog-service",
    }

    for key in scenarios:
        res = client.get(f"/api/scenarios/{key}/postmortem")
        assert res.status_code == 200
        data = res.json()

        assert "postmortem" in data
        assert "markdown" in data

        pm = data["postmortem"]
        assert pm["postmortem_id"]
        assert pm["incident_id"]
        assert pm["title"].startswith("Postmortem:")
        assert pm["service_name"] == expected_services[key]
        assert pm["status"] == "PUBLISHED"
        assert len(pm["executive_summary"]) > 50

        # Impact
        impact = pm["impact"]
        assert impact["affected_service"] == expected_services[key]
        assert impact["total_downtime_minutes"] > 0
        assert impact["impacted_customers_or_flows"]

        # Root cause
        rc = pm["root_cause"]
        assert rc["title"]
        assert rc["category"]
        assert rc["trigger_event"]
        assert rc["causal_chain"]

        # Five Whys
        assert len(pm["five_whys"]) >= 2

        # Timeline milestones
        assert len(pm["timeline_milestones"]) >= 3

        # Action Items
        assert len(pm["action_items"]) >= 1
        for act in pm["action_items"]:
            assert act["id"]
            assert act["title"]
            assert act["category"]
            assert act["priority"] in ("P0", "P1", "P2", "P3")
            assert act["owner"]
            assert act["verification"]

        # Lessons Learned
        assert len(pm["lessons_learned_what_went_well"]) >= 1
        assert len(pm["lessons_learned_what_went_wrong"]) >= 1
        assert len(pm["lessons_learned_where_we_got_lucky"]) >= 1

        # Markdown check
        md = data["markdown"]
        assert "## 1. Executive Summary" in md
        assert "## 2. Impact" in md
        assert "## 3. Root Cause Analysis" in md
        assert "## 4. Five-Whys" in md
        assert "## 5. Chronological Incident Event Timeline" in md
        assert "## 6. Remediation" in md
        assert "## 7. Preventative Action Items" in md
        assert "## 8. Lessons Learned" in md


def test_stage4e_scenario_switching_state_isolation():
    """Verify postmortem generation is cleanly isolated across consecutive scenario requests."""
    # Scenario 1: oom_kill
    res_oom = client.get("/api/scenarios/oom_kill/postmortem")
    assert res_oom.status_code == 200
    pm_oom = res_oom.json()["postmortem"]
    assert pm_oom["service_name"] == "worker-service"
    assert "Memory Exhaustion" in pm_oom["title"]

    # Scenario 2: dependency_deadlock
    res_deadlock = client.get("/api/scenarios/dependency_deadlock/postmortem")
    assert res_deadlock.status_code == 200
    pm_deadlock = res_deadlock.json()["postmortem"]
    assert pm_deadlock["service_name"] == "checkout-service"
    assert "Thread Pool Starvation" in pm_deadlock["title"]
    assert pm_deadlock["service_name"] != pm_oom["service_name"]

    # Scenario 3: config_drift
    res_drift = client.get("/api/scenarios/config_drift/postmortem")
    assert res_drift.status_code == 200
    pm_drift = res_drift.json()["postmortem"]
    assert pm_drift["service_name"] == "auth-service"
    assert "JWKS" in pm_drift["title"]
    assert pm_drift["service_name"] != pm_deadlock["service_name"]


def test_stage4e_postmortem_five_whys_grounding_preservation():
    """Verify that Five Whys within postmortems retain evidence_ref and is_inferred flags."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

    for key in scenarios:
        res = client.get(f"/api/scenarios/{key}/postmortem")
        assert res.status_code == 200
        five_whys = res.json()["postmortem"]["five_whys"]

        assert len(five_whys) >= 2
        for idx, step in enumerate(five_whys):
            assert step["level"] == idx + 1
            assert step["why"]
            assert step["because"]
            if step["is_inferred"]:
                assert step["is_inferred"] is True
            else:
                assert step["evidence_ref"] is not None and len(step["evidence_ref"]) > 0


def test_stage4e_postmortem_json_and_markdown_exports_consistent():
    """Verify that exported postmortem JSON validates strictly against Pydantic schema."""
    res = client.get("/api/scenarios/oom_kill/postmortem")
    assert res.status_code == 200
    pm_dict = res.json()["postmortem"]

    # Validate against AeroPostmortem model
    pm_obj = AeroPostmortem.model_validate(pm_dict)
    assert pm_obj.postmortem_id.startswith("PM-")
    assert pm_obj.service_name == "worker-service"
    assert len(pm_obj.action_items) == 3


def test_stage4e_postmortem_nonexistent_scenario_404():
    """Verify 404 response for nonexistent scenario postmortem requests."""
    res = client.get("/api/scenarios/nonexistent_scenario_key/postmortem")
    assert res.status_code == 404

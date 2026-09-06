"""Tests for Stage 4D: Root Cause Analysis, Evidence Grounding, Five Whys & Safe Remediation."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_stage4d_diagnostic_static_assets_serve():
    """Verify all Stage 4D CSS and JS component modules are served cleanly."""
    # CSS
    res_css = client.get("/css/diagnostic.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".rca-workspace" in res_css.text
    assert ".five-whys-section" in res_css.text
    assert ".grounding-workspace" in res_css.text
    assert ".remediation-workspace" in res_css.text
    assert ".dry-run-terminal-card" in res_css.text

    # JS Components
    components = [
        "diagnostic.js",
        "five_whys.js",
        "grounding_scorecard.js",
        "remediation.js",
        "dry_run_console.js",
    ]
    for comp in components:
        res_js = client.get(f"/js/components/{comp}")
        assert res_js.status_code == 200, f"Failed to load /js/components/{comp}"
        assert "application/javascript" in res_js.headers.get("content-type", "")
        assert len(res_js.text) > 50


def test_stage4d_scenario_diagnose_endpoints_all_scenarios():
    """Verify diagnosis endpoints return structured root cause and grounding for all 5 scenarios."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

    expected_categories = {
        "oom_kill": "RESOURCE_EXHAUSTION_MEMORY",
        "db_pool_exhaustion": "DATABASE_CONNECTION_EXHAUSTION",
        "config_drift": "CONFIGURATION_DRIFT",
        "dependency_deadlock": "DEPENDENCY_OUTAGE_TIMEOUT",
        "cache_poisoning": "CACHE_STAMPEDE_SERIALIZATION",
    }

    for key in scenarios:
        res = client.get(f"/api/scenarios/{key}/diagnose")
        assert res.status_code == 200
        data = res.json()

        assert "report" in data
        assert "grounding" in data
        assert "duration_sec" in data

        report = data["report"]
        assert report["incident_id"]
        assert report["service_name"]
        assert report["severity"]
        assert report["probable_root_cause"]["title"]
        assert report["probable_root_cause"]["category"] == expected_categories[key]
        assert report["confidence_level"]["score"] >= 0.90
        assert report["confidence_level"]["rating"] == "HIGH"
        assert len(report["supporting_evidence"]) >= 2

        rem = report["recommended_remediation"]
        assert len(rem["immediate_steps"]) >= 1
        assert rem["verification_metric"]
        assert rem["rollback_plan"]


def test_stage4d_five_whys_grounding_and_depth_invariants():
    """Verify that every Five Whys step is traceable to concrete evidence OR explicitly labeled as derived inference."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

    for key in scenarios:
        res = client.get(f"/api/scenarios/{key}/diagnose")
        assert res.status_code == 200
        report = res.json()["report"]

        five_whys = report.get("five_whys", [])
        assert len(five_whys) >= 2, f"Scenario {key} has too few Five Whys steps ({len(five_whys)})"
        assert len(five_whys) <= 5, f"Scenario {key} exceeds maximum Five Whys depth 5"

        for idx, step in enumerate(five_whys):
            assert step["level"] == idx + 1, f"Step level {step['level']} out of order at index {idx}"
            assert step["why"] and len(step["why"].strip()) > 5, f"Missing or short 'why' in {key} step {step['level']}"
            assert step["because"] and len(step["because"].strip()) > 5, f"Missing or short 'because' in {key} step {step['level']}"

            # Invariant: Every step MUST be traceable to evidence OR explicitly marked as derived inference
            if step["is_inferred"]:
                assert step["is_inferred"] is True
            else:
                assert step["evidence_ref"] is not None and len(step["evidence_ref"].strip()) > 0, (
                    f"Non-inferred step {step['level']} in {key} missing evidence_ref"
                )


def test_stage4d_grounding_verification_and_evaluation_endpoint():
    """Verify quantitative evaluation metrics (Recall, Precision, Hallucination Rate) across all scenarios."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

    for key in scenarios:
        res = client.get(f"/api/scenarios/{key}/evaluation")
        assert res.status_code == 200
        scorecard = res.json()

        assert scorecard["scenario_id"].startswith("BENCHMARK-")
        assert scorecard["scenario_name"]
        assert scorecard["root_cause_accuracy"] == 1.0

        assert scorecard["root_cause_category_match"] is True
        assert scorecard["grounding_recall"] >= 0.80
        assert scorecard["grounding_precision"] >= 0.80
        assert scorecard["hallucination_rate"] <= 0.05
        assert scorecard["is_benchmark_passed"] is True

        gv = scorecard["grounding_verification"]
        assert gv["is_fully_grounded"] is True
        assert gv["unverified_count"] == 0
        assert len(gv["evidence_details"]) >= 2


def test_stage4d_remediation_simulation_safety_invariants():
    """Safety Invariant: Diagnosis and Remediation Simulation must NEVER execute subprocesses, commands, or mutate infrastructure."""
    with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run, patch("os.system") as mock_system:
        scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]

        for key in scenarios:
            res = client.get(f"/api/scenarios/{key}/diagnose")
            assert res.status_code == 200

            res_eval = client.get(f"/api/scenarios/{key}/evaluation")
            assert res_eval.status_code == 200

        # Safety invariant check: zero subprocess/shell execution occurred
        mock_popen.assert_not_called()
        mock_run.assert_not_called()
        mock_system.assert_not_called()


def test_stage4d_scenario_switching_state_isolation():
    """Verify diagnosis and Five Whys reports are cleanly isolated across consecutive scenario requests."""
    res1 = client.get("/api/scenarios/oom_kill/diagnose")
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["report"]["service_name"] == "worker-service"
    assert "ExitCode 137" in d1["report"]["incident_summary"]

    res2 = client.get("/api/scenarios/config_drift/diagnose")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["report"]["service_name"] == "auth-service"
    assert "JWKS" in d2["report"]["incident_summary"]
    assert d2["report"]["service_name"] != d1["report"]["service_name"]


def test_stage4d_missing_or_invalid_scenario_404():
    """Verify 404 response for nonexistent scenario keys."""
    res_diag = client.get("/api/scenarios/nonexistent_scenario_key/diagnose")
    assert res_diag.status_code == 404

    res_eval = client.get("/api/scenarios/nonexistent_scenario_key/evaluation")
    assert res_eval.status_code == 404

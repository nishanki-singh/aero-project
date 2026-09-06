"""Tests for AERO Phase 4 Stage 4F: Grounded SRE Copilot."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.service import AeroService
from src.chat.engine import MockCopilotEngine, VertexAiCopilotEngine
from src.chat.grounding import CopilotGroundingVerifier
from src.chat.prompts import build_copilot_prompt
from src.schemas.chat import ChatRequest, ChatResponse, EvidenceItem
from src.schemas.diagnostic import SignalType

client = TestClient(app)


def test_chat_schema_validation():
    """Verify Pydantic models for ChatRequest, ChatResponse, and EvidenceItem."""
    item = EvidenceItem(
        signal_type=SignalType.LOG,
        source="worker-service",
        description="ExitCode 137 (OOMKilled)",
        log_snippet="ExitCode 137",
    )
    assert item.signal_type == SignalType.LOG
    assert item.source == "worker-service"

    req = ChatRequest(
        scenario_key="oom_kill",
        message="What caused the failure?",
    )
    assert req.scenario_key == "oom_kill"
    assert req.provider == "mock"

    resp = ChatResponse(
        scenario_key="oom_kill",
        answer="Worker service experienced memory saturation.",
        evidence=[item],
        inferences=["JVM heap exceeded limit."],
        recommendations=["Increase container memory."],
        confidence=0.95,
        grounded=True,
    )
    assert resp.grounded is True
    assert len(resp.evidence) == 1
    assert len(resp.inferences) == 1
    assert len(resp.recommendations) == 1


def test_mock_copilot_engine_all_scenarios():
    """Verify that MockCopilotEngine produces structured responses for all 5 scenarios."""
    scenarios = ["oom_kill", "db_pool_exhaustion", "config_drift", "dependency_deadlock", "cache_poisoning"]
    engine = MockCopilotEngine()

    for key in scenarios:
        bundle = AeroService.get_scenario_bundle(key, seed=42)
        incident = bundle.incident
        diag_resp = AeroService.diagnose(incident)
        timeline = AeroService.synthesize_timeline(incident, diag_resp.report)

        resp = engine.ask(incident, diag_resp.report, timeline, "What caused this incident?", key)
        assert isinstance(resp, ChatResponse)
        assert resp.scenario_key == key
        assert len(resp.answer) > 20
        assert len(resp.evidence) >= 1
        assert len(resp.inferences) >= 1
        assert len(resp.recommendations) >= 1
        assert resp.grounded is True

        # Verify grounding against active telemetry
        is_grounded, failed_claims = CopilotGroundingVerifier.verify(resp, incident)
        assert is_grounded is True, f"Scenario {key} had ungrounded claims: {failed_claims}"


def test_copilot_root_cause_questions():
    """Verify root cause queries return scenario-specific causal answers and evidence."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    incident = bundle.incident
    diag_resp = AeroService.diagnose(incident)
    timeline = AeroService.synthesize_timeline(incident, diag_resp.report)

    engine = MockCopilotEngine()
    resp = engine.ask(incident, diag_resp.report, timeline, "What caused the outage?", "oom_kill")

    assert "OOM" in resp.answer or "Memory" in resp.answer or "Heap" in resp.answer
    assert any(e.signal_type == SignalType.LOG for e in resp.evidence)
    assert any(e.signal_type == SignalType.METRIC for e in resp.evidence)


def test_copilot_evidence_questions():
    """Verify evidence queries return verified telemetry signals with citations."""
    bundle = AeroService.get_scenario_bundle("db_pool_exhaustion", seed=42)
    incident = bundle.incident
    diag_resp = AeroService.diagnose(incident)
    timeline = AeroService.synthesize_timeline(incident, diag_resp.report)

    engine = MockCopilotEngine()
    resp = engine.ask(incident, diag_resp.report, timeline, "Show me the strongest evidence.", "db_pool_exhaustion")

    assert "order-service" in resp.answer
    assert len(resp.evidence) >= 2
    assert any("database/pool/active_connections" in (e.metric_name or "") for e in resp.evidence)


def test_copilot_timeline_and_change_questions():
    """Verify change/deployment questions correctly identify deployments or lack thereof."""
    engine = MockCopilotEngine()

    # oom_kill: 0 deployments
    bundle_oom = AeroService.get_scenario_bundle("oom_kill", seed=42)
    resp_oom = engine.ask(bundle_oom.incident, None, None, "What changed before the incident?", "oom_kill")
    assert "No recent code deployments" in resp_oom.answer or "Zero deployment" in resp_oom.evidence[0].description

    # db_pool_exhaustion: v2.4.1 deployment
    bundle_db = AeroService.get_scenario_bundle("db_pool_exhaustion", seed=42)
    resp_db = engine.ask(bundle_db.incident, None, None, "When was the last release?", "db_pool_exhaustion")
    assert "v2.4.1" in resp_db.answer or any("v2.4.1" in e.description for e in resp_db.evidence)


def test_copilot_remediation_verification_questions():
    """Verify remediation questions emphasize dry-run simulation and rollback targets."""
    bundle = AeroService.get_scenario_bundle("config_drift", seed=42)
    engine = MockCopilotEngine()
    resp = engine.ask(bundle.incident, None, None, "What should I verify before remediation?", "config_drift")

    assert "dry-run" in resp.answer.lower() or "simulation" in resp.answer.lower()
    assert any("dry-run" in r.lower() or "simulation" in r.lower() for r in resp.recommendations)
    assert any("rollback" in r.lower() for r in resp.recommendations)


def test_copilot_unsupported_question_handling():
    """Verify Copilot explicitly states evidence is unavailable for unrelated topics rather than hallucinating."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    engine = MockCopilotEngine()
    resp = engine.ask(bundle.incident, None, None, "What is the weather forecast in Tokyo?", "oom_kill")

    assert "No telemetry or diagnostic evidence" in resp.answer
    assert len(resp.evidence) == 0
    assert "not present in the active" in resp.inferences[0]


def test_copilot_grounding_verifier_valid_claims():
    """Verify GroundingVerifier passes when all evidence exists in telemetry."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    incident = bundle.incident

    valid_response = ChatResponse(
        scenario_key="oom_kill",
        answer="Memory saturation observed.",
        evidence=[
            EvidenceItem(
                signal_type=SignalType.METRIC,
                source="container/memory_utilization",
                metric_name="container/memory_utilization",
                description="container/memory_utilization reached 100%",
            ),
            EvidenceItem(
                signal_type=SignalType.LOG,
                source="worker-service",
                description="ExitCode 137 (OOMKilled)",
                log_snippet="ExitCode 137",
            ),
        ],
        inferences=["JVM heap space was exhausted."],
        recommendations=["Increase memory limit."],
        grounded=True,
    )

    is_grounded, failed_claims = CopilotGroundingVerifier.verify(valid_response, incident)
    assert is_grounded is True
    assert len(failed_claims) == 0


def test_copilot_grounding_verifier_catches_hallucinations():
    """Verify GroundingVerifier flags fabricated metrics and nonexistent log lines."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    incident = bundle.incident

    hallucinated_response = ChatResponse(
        scenario_key="oom_kill",
        answer="Fabricated incident claims.",
        evidence=[
            EvidenceItem(
                signal_type=SignalType.METRIC,
                source="fake/nonexistent_cpu_core_metric",
                metric_name="fake/nonexistent_cpu_core_metric",
                description="fake metric spiked",
            ),
            EvidenceItem(
                signal_type=SignalType.LOG,
                source="worker-service",
                description="Quantum cosmic ray bitflip encountered",
                log_snippet="Quantum cosmic ray bitflip encountered",
            ),
        ],
        inferences=["Fake inference."],
        recommendations=["Fake recommendation."],
        grounded=True,
    )

    is_grounded, failed_claims = CopilotGroundingVerifier.verify(hallucinated_response, incident)
    assert is_grounded is False
    assert len(failed_claims) == 2


def test_copilot_scenario_switching_isolation():
    """Verify consecutive Copilot requests across scenarios are completely isolated."""
    # Query Scenario A: oom_kill
    res_a = client.post("/api/chat", json={"scenario_key": "oom_kill", "message": "What caused this incident?"})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["scenario_key"] == "oom_kill"
    assert "worker-service" in data_a["answer"] or any("worker-service" in e["source"] for e in data_a["evidence"])

    # Query Scenario B: dependency_deadlock
    res_b = client.post("/api/chat", json={"scenario_key": "dependency_deadlock", "message": "What caused this incident?"})
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["scenario_key"] == "dependency_deadlock"
    assert "checkout-service" in data_b["answer"] or any("checkout-service" in e["source"] for e in data_b["evidence"])

    # Confirm no oom_kill or worker-service leakage in dependency_deadlock
    assert "worker-service" not in data_b["answer"]
    assert "ExitCode 137" not in str(data_b["evidence"])


def test_api_chat_endpoint_success():
    """Verify POST /api/chat returns structured ChatResponse."""
    payload = {
        "scenario_key": "db_pool_exhaustion",
        "message": "What evidence supports the diagnosis?",
        "provider": "mock",
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["scenario_key"] == "db_pool_exhaustion"
    assert len(data["answer"]) > 0
    assert len(data["evidence"]) >= 1
    assert len(data["inferences"]) >= 1
    assert len(data["recommendations"]) >= 1
    assert data["grounded"] is True


def test_api_chat_empty_message_400():
    """Verify POST /api/chat rejects empty or whitespace-only messages with HTTP 400."""
    res = client.post("/api/chat", json={"scenario_key": "oom_kill", "message": "   "})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_api_chat_unknown_scenario_404():
    """Verify POST /api/chat returns HTTP 404 for nonexistent scenario keys."""
    res = client.post("/api/chat", json={"scenario_key": "nonexistent_scenario_key", "message": "Hello"})
    assert res.status_code == 404


def test_copilot_safety_invariants_no_subprocess_mutation(monkeypatch):
    """Verify Copilot execution NEVER calls subprocess, shell, gcloud, or kubectl commands."""
    import subprocess

    def forbidden_call(*args, **kwargs):
        raise AssertionError("Copilot attempted to invoke subprocess or shell command!")

    monkeypatch.setattr(subprocess, "run", forbidden_call)
    monkeypatch.setattr(subprocess, "Popen", forbidden_call)

    # Run chat query
    res = client.post("/api/chat", json={"scenario_key": "oom_kill", "message": "What should I do?"})
    assert res.status_code == 200
    assert res.json()["grounded"] is True


def test_copilot_safety_invariant_no_remediation_simulator_mutation():
    """Verify Copilot answers are advisory only and never mutate or auto-trigger the remediation simulator."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    engine = MockCopilotEngine()
    resp = engine.ask(bundle.incident, None, None, "Apply the fix immediately", "oom_kill")

    assert isinstance(resp, ChatResponse)
    # The answer should never claim that remediation was automatically executed
    assert "executed" not in resp.answer.lower() or "dry-run" in resp.answer.lower()
    # Recommendations should instruct user to verify in dry-run mode
    assert any("dry-run" in r.lower() or "verify" in r.lower() for r in resp.recommendations)


def test_copilot_static_assets_serve():
    """Verify copilot CSS and JS component modules serve cleanly via FastAPI."""
    res_css = client.get("/css/copilot.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert ".copilot-drawer" in res_css.text
    assert ".copilot-evidence-block" in res_css.text
    assert ".copilot-inference-block" in res_css.text
    assert ".copilot-recommendation-block" in res_css.text

    res_js = client.get("/js/components/copilot_chat.js")
    assert res_js.status_code == 200
    assert "application/javascript" in res_js.headers.get("content-type", "")
    assert "initCopilotDrawer" in res_js.text
    assert "toggleCopilotDrawer" in res_js.text


def test_copilot_drawer_resize_affordance_and_behavior():
    """Verify Copilot drawer includes resize handle affordance, expand/restore toggle, and drag listeners."""
    res_css = client.get("/css/copilot.css")
    assert res_css.status_code == 200
    assert ".copilot-resize-handle" in res_css.text
    assert "col-resize" in res_css.text
    assert ".copilot-drawer.is-resizing" in res_css.text
    assert "min-width" in res_css.text

    res_js = client.get("/js/components/copilot_chat.js")
    assert res_js.status_code == 200
    assert "copilot-resize-handle" in res_js.text
    assert "setupDrawerResize" in res_js.text
    assert "btn-copilot-expand" in res_js.text
    assert "pointerdown" in res_js.text
    assert "pointermove" in res_js.text
    assert "pointerup" in res_js.text


def test_vertex_copilot_engine_wiring_static():
    """Verify VertexAiCopilotEngine initialization and prompt builder without live network calls."""
    engine = VertexAiCopilotEngine(
        project_id="test-project",
        region="us-central1",
        model_name="gemini-2.5-flash",
    )
    assert engine.project_id == "test-project"
    assert engine.region == "us-central1"
    assert engine.model_name == "gemini-2.5-flash"

    # Verify prompt builder
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    prompt = build_copilot_prompt(bundle.incident, None, None, "What caused the incident?")
    assert "INCIDENT CONTEXT:" in prompt
    assert "worker-service" in prompt
    assert "What caused the incident?" in prompt

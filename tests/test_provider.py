"""Comprehensive tests for AERO Provider Toggle and Engine Selection.

Verifies:
1. Deterministic factory engine selection (Mock vs Vertex AI).
2. Strict elimination of silent Live -> Mock fallback.
3. Explicit error propagation when Live Vertex calls fail.
4. Correct provider metadata in API response models (Chat, Diagnose, Postmortem).
5. Provider propagation across REST routes and frontend client contracts.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.service import AeroService
from src.chat.engine import (
    MockCopilotEngine,
    VertexAiCopilotEngine,
    get_copilot_engine,
)
from src.engine.diagnostic_engine import (
    MockDiagnosticEngine,
    VertexAiDiagnosticEngine,
    get_diagnostic_engine,
)
from src.postmortem.engine import (
    MockPostmortemEngine,
    VertexAiPostmortemEngine,
    get_postmortem_engine,
)
from src.schemas.chat import ChatResponse

client = TestClient(app)


# -----------------------------------------------------------------------------
# A. Copilot Provider Selection
# -----------------------------------------------------------------------------


def test_copilot_provider_selection_mock():
    """Verify provider='mock' deterministically returns MockCopilotEngine."""
    engine = get_copilot_engine(provider="mock")
    assert isinstance(engine, MockCopilotEngine)

    engine_det = get_copilot_engine(provider="deterministic")
    assert isinstance(engine_det, MockCopilotEngine)


def test_copilot_provider_selection_live():
    """Verify provider='live' or 'vertex' or 'gemini' returns VertexAiCopilotEngine."""
    for prov in ("live", "vertex", "gemini", "LIVE", "Vertex"):
        engine = get_copilot_engine(provider=prov)
        assert isinstance(engine, VertexAiCopilotEngine)


# -----------------------------------------------------------------------------
# B. Diagnosis Provider Selection
# -----------------------------------------------------------------------------


def test_diagnostic_provider_selection_mock():
    """Verify provider='mock' deterministically returns MockDiagnosticEngine."""
    engine = get_diagnostic_engine(provider="mock")
    assert isinstance(engine, MockDiagnosticEngine)

    engine_det = get_diagnostic_engine(provider="deterministic")
    assert isinstance(engine_det, MockDiagnosticEngine)


def test_diagnostic_provider_selection_live():
    """Verify provider='live' or 'vertex' or 'gemini' returns VertexAiDiagnosticEngine."""
    for prov in ("live", "vertex", "gemini", "LIVE", "Vertex"):
        engine = get_diagnostic_engine(provider=prov)
        assert isinstance(engine, VertexAiDiagnosticEngine)


# -----------------------------------------------------------------------------
# C. Postmortem Provider Selection
# -----------------------------------------------------------------------------


def test_postmortem_provider_selection_mock():
    """Verify provider='mock' deterministically returns MockPostmortemEngine."""
    engine = get_postmortem_engine(provider="mock")
    assert isinstance(engine, MockPostmortemEngine)

    engine_det = get_postmortem_engine(provider="deterministic")
    assert isinstance(engine_det, MockPostmortemEngine)


def test_postmortem_provider_selection_live():
    """Verify provider='live' or 'vertex' or 'gemini' returns VertexAiPostmortemEngine."""
    for prov in ("live", "vertex", "gemini", "LIVE", "Vertex"):
        engine = get_postmortem_engine(provider=prov)
        assert isinstance(engine, VertexAiPostmortemEngine)


# -----------------------------------------------------------------------------
# D. Strict Elimination of Silent Live -> Mock Fallback
# -----------------------------------------------------------------------------


def test_explicit_live_copilot_failure_raises_error(monkeypatch):
    """Verify that when provider='live' fails, it raises an explicit error and NEVER executes Mock."""

    def mock_fail_ask(*args, **kwargs):
        raise ConnectionError("Vertex AI endpoint unreachable / invalid credentials")

    monkeypatch.setattr(VertexAiCopilotEngine, "ask", mock_fail_ask)

    # Calling AeroService.chat directly with provider='live' must raise ConnectionError
    with pytest.raises(ConnectionError, match="Vertex AI endpoint unreachable"):
        AeroService.chat(
            scenario_key="oom_kill",
            message="What happened?",
            provider="live",
        )

    # Calling POST /api/chat with provider='live' must return HTTP 500 error, not a mock response
    res = client.post(
        "/api/chat",
        json={
            "scenario_key": "oom_kill",
            "message": "What happened?",
            "provider": "live",
        },
    )
    assert res.status_code == 500
    assert "Vertex AI endpoint unreachable" in res.json()["detail"]


def test_explicit_live_diagnosis_failure_raises_error(monkeypatch):
    """Verify that when provider='live' fails during diagnosis, it raises an error and NEVER executes Mock."""

    def mock_fail_diagnose(*args, **kwargs):
        raise RuntimeError("Vertex AI quota exceeded (429 ResourceExhausted)")

    monkeypatch.setattr(VertexAiDiagnosticEngine, "diagnose", mock_fail_diagnose)

    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)

    with pytest.raises(RuntimeError, match="ResourceExhausted"):
        AeroService.diagnose(bundle.incident, provider="live")

    # REST endpoint check
    res = client.get("/api/scenarios/oom_kill/diagnose?provider=live")
    # Should propagate error (500 or uncaught in test client raising exception)
    assert res.status_code in (500, 400) or "ResourceExhausted" in str(res.text)


def test_explicit_live_postmortem_failure_raises_error(monkeypatch):
    """Verify that when provider='live' fails during postmortem, it raises an error and NEVER executes Mock."""

    def mock_fail_pm(*args, **kwargs):
        raise RuntimeError("Vertex AI Gemini model unavailable")

    monkeypatch.setattr(VertexAiPostmortemEngine, "generate_postmortem", mock_fail_pm)

    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)

    with pytest.raises(RuntimeError, match="Gemini model unavailable"):
        AeroService.generate_postmortem(bundle.incident, provider="live")


# -----------------------------------------------------------------------------
# E. Provider Metadata in API Responses
# -----------------------------------------------------------------------------


def test_api_chat_provider_metadata_mock():
    """Verify POST /api/chat with provider='mock' returns provider='mock' metadata."""
    res = client.post(
        "/api/chat",
        json={
            "scenario_key": "oom_kill",
            "message": "What caused this?",
            "provider": "mock",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "mock"
    assert data["grounded"] is True


def test_api_chat_provider_metadata_live_mocked(monkeypatch):
    """Verify POST /api/chat with provider='live' returns provider='live' metadata when successful."""
    mock_resp = ChatResponse(
        scenario_key="oom_kill",
        answer="[LIVE VERTEX] OOM killed worker-service container.",
        evidence=[],
        inferences=["Live inference"],
        recommendations=["Live recommendation"],
        provider="live",
        grounded=True,
    )

    monkeypatch.setattr(VertexAiCopilotEngine, "ask", MagicMock(return_value=mock_resp))

    res = client.post(
        "/api/chat",
        json={
            "scenario_key": "oom_kill",
            "message": "What caused this?",
            "provider": "live",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "live"
    assert "[LIVE VERTEX]" in data["answer"]


def test_api_scenario_diagnose_provider_metadata_mock():
    """Verify GET /api/scenarios/{id}/diagnose returns provider='mock'."""
    res = client.get("/api/scenarios/oom_kill/diagnose?provider=mock")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "mock"
    assert data["report"]["service_name"] == "worker-service"


def test_api_scenario_diagnose_provider_metadata_live_mocked(monkeypatch):
    """Verify GET /api/scenarios/{id}/diagnose with provider='live' returns provider='live'."""
    # Obtain a valid base report from mock engine and modify summary
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    mock_report = MockDiagnosticEngine().diagnose(bundle.incident)
    mock_report.incident_summary = "[LIVE VERTEX] Worker service crash"

    monkeypatch.setattr(VertexAiDiagnosticEngine, "diagnose", MagicMock(return_value=mock_report))

    res = client.get("/api/scenarios/oom_kill/diagnose?provider=live")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "live"
    assert data["report"]["incident_summary"] == "[LIVE VERTEX] Worker service crash"


def test_api_scenario_postmortem_provider_metadata_mock():
    """Verify GET /api/scenarios/{id}/postmortem returns provider='mock'."""
    res = client.get("/api/scenarios/oom_kill/postmortem?provider=mock")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "mock"
    assert "INC-" in data["postmortem"]["incident_id"]


def test_api_scenario_postmortem_provider_metadata_live_mocked(monkeypatch):
    """Verify GET /api/scenarios/{id}/postmortem with provider='live' returns provider='live'."""
    bundle = AeroService.get_scenario_bundle("oom_kill", seed=42)
    diag = MockDiagnosticEngine().diagnose(bundle.incident)
    timeline = AeroService.synthesize_timeline(bundle.incident, diag)
    mock_pm = MockPostmortemEngine().generate_postmortem(bundle.incident, diag, timeline)
    mock_pm.title = "[LIVE VERTEX] Postmortem Report"

    monkeypatch.setattr(VertexAiPostmortemEngine, "generate_postmortem", MagicMock(return_value=mock_pm))

    res = client.get("/api/scenarios/oom_kill/postmortem?provider=live")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "live"
    assert data["postmortem"]["title"] == "[LIVE VERTEX] Postmortem Report"


# -----------------------------------------------------------------------------
# F. Frontend Client & Static Contracts
# -----------------------------------------------------------------------------


def test_frontend_api_client_contains_provider_parameters():
    """Verify that src/web/js/api.js defines provider parameters across all AI operations."""
    res = client.get("/js/api.js")
    assert res.status_code == 200
    content = res.text

    # Verify sendChatMessage accepts provider and passes it in POST body
    assert "sendChatMessage(scenarioKey, message, provider" in content
    assert "provider," in content

    # Verify getScenarioDiagnosis accepts provider and passes it in query
    assert "getScenarioDiagnosis(scenarioKey, provider" in content
    assert "providerParam" in content

    # Verify getScenarioEvaluation accepts provider
    assert "getScenarioEvaluation(scenarioKey, provider" in content

    # Verify getScenarioPostmortem accepts provider
    assert "getScenarioPostmortem(scenarioKey, provider" in content

    # Verify runDiagnosis accepts provider
    assert "runDiagnosis(incident, provider" in content


def test_frontend_copilot_chat_reads_provider_mode():
    """Verify that src/web/js/components/copilot_chat.js reads store.providerMode and passes it to API."""
    res = client.get("/js/components/copilot_chat.js")
    assert res.status_code == 200
    content = res.text

    assert "state.providerMode" in content
    assert "api.sendChatMessage(scenarioKey, userMessage.trim(), provider)" in content
    assert "Live Vertex AI" in content
    assert "Deterministic Mock" in content


def test_frontend_app_passes_provider_mode_on_load_and_switch():
    """Verify that src/web/js/app.js extracts providerMode from store for parallel AI fetches."""
    res = client.get("/js/app.js")
    assert res.status_code == 200
    content = res.text

    assert "store.getState().providerMode" in content
    assert "api.getScenarioDiagnosis(scenarioKey, currentProvider)" in content
    assert "api.getScenarioEvaluation(scenarioKey, currentProvider)" in content
    assert "api.getScenarioPostmortem(scenarioKey, currentProvider)" in content

"""Unit tests for the diagnostic reasoning engine and prompt assembly."""

from src.benchmark.scenarios.config_drift import generate_config_drift_scenario
from src.engine.correlator import TelemetryCorrelator
from src.engine.diagnostic_engine import MockDiagnosticEngine, VertexAiDiagnosticEngine, get_diagnostic_engine
from src.engine.prompts import build_diagnostic_prompt
from src.schemas.diagnostic import AeroDiagnosticReport


def test_build_diagnostic_prompt():
    """Verifies that diagnostic prompt contains all structured telemetry sections."""
    bundle = generate_config_drift_scenario(seed=42)
    incident = bundle.incident
    summary = TelemetryCorrelator.correlate(incident)

    prompt = build_diagnostic_prompt(incident, summary)

    assert "INCIDENT CONTEXT" in prompt
    assert incident.metadata.incident_id in prompt
    assert "auth-service" in prompt
    assert "config-rev-42" in prompt
    assert "UnknownHostException" in prompt
    assert "DIAGNOSTIC INSTRUCTIONS" in prompt


def test_mock_diagnostic_engine_generates_valid_report():
    """Verifies that MockDiagnosticEngine produces schema-valid, grounded diagnostic reports."""
    bundle = generate_config_drift_scenario(seed=42)
    incident = bundle.incident

    engine = MockDiagnosticEngine()
    report = engine.diagnose(incident)

    assert isinstance(report, AeroDiagnosticReport)
    assert report.incident_id == incident.metadata.incident_id
    assert report.probable_root_cause.category == "CONFIGURATION_DRIFT"
    assert report.confidence_level.score >= 0.90
    assert len(report.supporting_evidence) >= 2
    assert len(report.recommended_remediation.immediate_steps) >= 2


def test_get_diagnostic_engine_factory():
    """Verifies engine factory creates mock and live instances properly."""
    mock_eng = get_diagnostic_engine(provider="mock")
    assert isinstance(mock_eng, MockDiagnosticEngine)

    vertex_eng = get_diagnostic_engine(provider="vertex")
    assert isinstance(vertex_eng, VertexAiDiagnosticEngine)

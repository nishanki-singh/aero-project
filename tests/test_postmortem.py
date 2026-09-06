"""Unit tests for the Google SRE postmortem generator and markdown exporter."""

from src.benchmark.scenarios.db_pool_exhaustion import (
    generate_db_pool_exhaustion_scenario,
)
from src.benchmark.scenarios.oom_kill import generate_oom_kill_scenario
from src.engine.diagnostic_engine import MockDiagnosticEngine
from src.postmortem.engine import MockPostmortemEngine, get_postmortem_engine
from src.postmortem.exporter import PostmortemExporter
from src.schemas.postmortem import AeroPostmortem
from src.timeline.synthesizer import TimelineSynthesizer


def test_mock_postmortem_generation_oom_kill():
    """Verifies that MockPostmortemEngine generates a complete, schema-valid postmortem for OOMKill."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident = bundle.incident
    diag_engine = MockDiagnosticEngine()
    diag_report = diag_engine.diagnose(incident)
    timeline = TimelineSynthesizer.synthesize(incident, diag_report)

    pm_engine = MockPostmortemEngine()
    postmortem = pm_engine.generate_postmortem(incident, diag_report, timeline)

    assert isinstance(postmortem, AeroPostmortem)
    assert postmortem.incident_id == incident.metadata.incident_id
    assert postmortem.service_name == "worker-service"
    assert postmortem.root_cause.category == "RESOURCE_EXHAUSTION_MEMORY"
    assert len(postmortem.five_whys) >= 4
    assert len(postmortem.action_items) >= 3
    assert len(postmortem.timeline_milestones) >= 5
    assert postmortem.remediation_performed is not None

    # Check 5-Whys numbering
    for i, fw in enumerate(postmortem.five_whys):
        assert fw.level == i + 1
        assert len(fw.why) > 0
        assert len(fw.because) > 0

    # Check Action Items have priorities and owners
    for act in postmortem.action_items:
        assert act.priority.value in ("P0", "P1", "P2", "P3")
        assert len(act.owner) > 0
        assert len(act.verification) > 0


def test_postmortem_exporter_markdown():
    """Verifies that PostmortemExporter converts AeroPostmortem into valid Markdown with all required sections."""
    bundle = generate_db_pool_exhaustion_scenario(seed=42)
    incident = bundle.incident
    diag_engine = MockDiagnosticEngine()
    diag_report = diag_engine.diagnose(incident)
    timeline = TimelineSynthesizer.synthesize(incident, diag_report)

    pm_engine = get_postmortem_engine(provider="mock")
    postmortem = pm_engine.generate_postmortem(incident, diag_report, timeline)

    md = PostmortemExporter.to_markdown(postmortem)

    assert f"# {postmortem.title}" in md
    assert "## 1. Executive Summary" in md
    assert "## 2. Impact & Blast Radius Assessment" in md
    assert "## 3. Root Cause Analysis" in md
    assert "## 4. Five-Whys Deep Causal Hierarchy" in md
    assert "## 5. Chronological Incident Event Timeline" in md
    assert "## 6. Remediation & Recovery Verification" in md
    assert "## 7. Preventative Action Items" in md
    assert "## 8. Lessons Learned & Blameless Reflections" in md
    assert "order-service" in md
    assert "DATABASE_CONNECTION_EXHAUSTION" in md


def test_postmortem_exporter_json():
    """Verifies that PostmortemExporter serializes and deserializes cleanly to/from JSON."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident = bundle.incident
    diag_report = MockDiagnosticEngine().diagnose(incident)
    timeline = TimelineSynthesizer.synthesize(incident, diag_report)

    postmortem = MockPostmortemEngine().generate_postmortem(incident, diag_report, timeline)
    json_str = PostmortemExporter.to_json(postmortem)

    # Validate deserialization back to model
    deserialized = AeroPostmortem.model_validate_json(json_str)
    assert deserialized.postmortem_id == postmortem.postmortem_id
    assert deserialized.incident_id == postmortem.incident_id
    assert len(deserialized.action_items) == len(postmortem.action_items)

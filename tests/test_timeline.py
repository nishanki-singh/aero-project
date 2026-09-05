"""Unit tests for the chronological incident timeline synthesizer and replay engine."""

from src.benchmark.scenarios.db_pool_exhaustion import (
    generate_db_pool_exhaustion_scenario,
)
from src.benchmark.scenarios.oom_kill import generate_oom_kill_scenario
from src.engine.diagnostic_engine import MockDiagnosticEngine
from src.schemas.timeline import IncidentReplaySeries, IncidentTimeline, MilestoneType
from src.timeline.replay import IncidentReplayProvider
from src.timeline.synthesizer import TimelineSynthesizer


def test_timeline_synthesizer_milestones():
    """Verifies that TimelineSynthesizer produces ordered milestones with lifecycle metrics."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident = bundle.incident
    diag_engine = MockDiagnosticEngine()
    report = diag_engine.diagnose(incident)

    timeline = TimelineSynthesizer.synthesize(incident, report)

    assert isinstance(timeline, IncidentTimeline)
    assert timeline.incident_id == incident.metadata.incident_id
    assert timeline.service_name == incident.metadata.affected_service
    assert timeline.total_duration_minutes > 0.0
    assert timeline.time_to_detect_minutes is not None
    assert timeline.time_to_mitigate_minutes is not None
    assert len(timeline.milestones) >= 5

    # Check milestone sequence
    milestone_types = [m.milestone_type for m in timeline.milestones]
    assert MilestoneType.ALERT_FIRED in milestone_types
    assert MilestoneType.TRIAGE_START in milestone_types
    assert MilestoneType.MITIGATION_APPLIED in milestone_types
    assert MilestoneType.RECOVERY_VERIFIED in milestone_types
    assert MilestoneType.RESOLVED in milestone_types

    # Ensure chronological ordering
    for i in range(len(timeline.milestones) - 1):
        assert timeline.milestones[i].timestamp <= timeline.milestones[i + 1].timestamp


def test_timeline_synthesizer_deployment_tracking():
    """Verifies that deployment events are captured as onset milestones."""
    bundle = generate_db_pool_exhaustion_scenario(seed=42)
    incident = bundle.incident

    timeline = TimelineSynthesizer.synthesize(incident)
    deploy_milestone = next(
        (m for m in timeline.milestones if m.source_signal == "DEPLOYMENT"),
        None,
    )

    assert deploy_milestone is not None
    assert "v2.4.1" in deploy_milestone.title or "v2.4.1" in deploy_milestone.description
    assert deploy_milestone.source_service == "order-service"


def test_incident_replay_provider():
    """Verifies that IncidentReplayProvider discretizes telemetry into ordered step snapshots."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident = bundle.incident

    replay = IncidentReplayProvider.generate_replay_series(incident, interval_seconds=60)

    assert isinstance(replay, IncidentReplaySeries)
    assert replay.incident_id == incident.metadata.incident_id
    assert replay.service_name == "worker-service"
    assert replay.interval_seconds == 60
    assert replay.total_steps > 0
    assert len(replay.snapshots) == replay.total_steps

    # Check first and last step
    first_step = replay.snapshots[0]
    assert first_step.step_index == 0
    assert first_step.health_status in ("HEALTHY", "DEGRADED", "CRITICAL", "RECOVERING")

    # Verify step indexing is monotonic
    for idx, snap in enumerate(replay.snapshots):
        assert snap.step_index == idx

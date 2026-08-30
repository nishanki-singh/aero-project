"""Unit tests for the 5 approved benchmark scenarios."""

import pytest
from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.schemas.diagnostic import SignalType


@pytest.mark.parametrize("scenario_name,generator_fn", list(BENCHMARK_SCENARIOS.items()))
def test_scenario_structure_and_ground_truth(scenario_name, generator_fn):
    """Verifies that each scenario produces a valid bundle with populated ground truth."""
    bundle = generator_fn(seed=42)

    # 1. Verify Ground Truth fields
    gt = bundle.ground_truth
    assert gt.scenario_id.startswith("BENCHMARK-")
    assert len(gt.scenario_name) > 0
    assert len(gt.category) > 0
    assert len(gt.affected_service) > 0
    assert len(gt.trigger_event) > 0
    assert len(gt.root_cause_summary) > 0
    assert len(gt.expected_evidence_signals) >= 3
    assert len(gt.expected_remediation.key_actions) >= 2
    assert len(gt.expected_remediation.expected_verification_metric) > 0

    # 2. Verify Incident Telemetry fields
    inc = bundle.incident
    assert inc.metadata.affected_service == gt.affected_service
    assert len(inc.telemetry.logs) > 50
    assert len(inc.telemetry.metrics) >= 2
    assert len(inc.telemetry.health_signals) > 0
    assert inc.telemetry.time_window_end > inc.telemetry.time_window_start


@pytest.mark.parametrize("scenario_name,generator_fn", list(BENCHMARK_SCENARIOS.items()))
def test_mandatory_evidence_present_in_telemetry(scenario_name, generator_fn):
    """Verifies that every mandatory expected evidence pattern is actually present in the generated telemetry."""
    bundle = generator_fn(seed=42)
    gt = bundle.ground_truth
    telemetry = bundle.incident.telemetry

    for ev in gt.expected_evidence_signals:
        if not ev.is_mandatory:
            continue

        found = False
        pattern = ev.pattern.lower()

        if ev.signal_type == SignalType.LOG:
            for log in telemetry.logs:
                if pattern in log.message.lower() or any(pattern in str(v).lower() for v in log.attributes.values()):
                    found = True
                    break
        elif ev.signal_type == SignalType.METRIC:
            for metric in telemetry.metrics:
                if pattern in metric.metric_name.lower() or any(pattern in str(v).lower() for v in metric.labels.values()):
                    found = True
                    break
        elif ev.signal_type == SignalType.DEPLOYMENT:
            for dep in telemetry.deployments:
                if pattern in dep.version.lower() or pattern in dep.change_summary.lower():
                    found = True
                    break
        elif ev.signal_type == SignalType.HEALTH:
            for h in telemetry.health_signals:
                if pattern in h.status.value.lower() or (h.details and pattern in h.details.lower()):
                    found = True
                    break

        assert found, f"Scenario '{scenario_name}' missing expected mandatory evidence: [{ev.signal_type.value}] '{ev.pattern}'"

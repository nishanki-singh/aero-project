"""Unit tests for the telemetry correlator and pre-filter pipeline."""

from src.benchmark.scenarios.oom_kill import generate_oom_kill_scenario
from src.engine.correlator import TelemetryCorrelator
from src.schemas.telemetry import LogLevel


def test_correlator_aggregates_signals():
    """Verifies that TelemetryCorrelator filters noise and extracts anomalies."""
    bundle = generate_oom_kill_scenario(seed=42)
    incident = bundle.incident

    summary = TelemetryCorrelator.correlate(incident)

    # 1. Verification of metadata pass-through
    assert summary.incident_id == incident.metadata.incident_id
    assert summary.affected_service == "worker-service"
    assert summary.total_raw_logs == len(incident.telemetry.logs)

    # 2. Verification of error log clustering
    assert len(summary.error_clusters) > 0
    # Must contain OOM / Heap error clusters
    has_oom_cluster = any(
        "outofmemory" in c.pattern_summary.lower() or "137" in c.pattern_summary
        for c in summary.error_clusters
    )
    assert has_oom_cluster

    # 3. Verification of metric anomalies
    assert len(summary.metric_anomalies) > 0
    mem_anomaly = next(
        (m for m in summary.metric_anomalies if "memory_utilization" in m.metric_name),
        None,
    )
    assert mem_anomaly is not None
    assert mem_anomaly.peak_value >= 99.0
    assert mem_anomaly.service_name == "worker-service"

    # 4. Verification of health degradation
    assert len(summary.health_degradations) > 0
    assert any(h.status.value == "UNHEALTHY" for h in summary.health_degradations)

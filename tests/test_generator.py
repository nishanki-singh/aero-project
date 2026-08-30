"""Unit tests for the synthetic incident generator engine."""

from datetime import datetime, timezone
from src.benchmark.generator import SyntheticIncidentGenerator


def test_generator_deterministic_seeding():
    """Verifies that identical random seeds produce byte-for-byte identical datasets."""
    t0 = datetime(2026, 8, 30, 14, 0, 0, tzinfo=timezone.utc)
    services = ["auth-service", "order-service"]

    gen1 = SyntheticIncidentGenerator(seed=123, base_time=t0)
    logs1 = gen1.generate_background_logs(services, t0, duration_minutes=10)
    metric1 = gen1.generate_baseline_metrics("auth-service", "cpu", "percent", t0, duration_minutes=10)

    gen2 = SyntheticIncidentGenerator(seed=123, base_time=t0)
    logs2 = gen2.generate_background_logs(services, t0, duration_minutes=10)
    metric2 = gen2.generate_baseline_metrics("auth-service", "cpu", "percent", t0, duration_minutes=10)

    assert len(logs1) == len(logs2)
    for l1, l2 in zip(logs1, logs2):
        assert l1.timestamp == l2.timestamp
        assert l1.message == l2.message
        assert l1.trace_id == l2.trace_id

    assert [p.value for p in metric1.points] == [p.value for p in metric2.points]


def test_generator_different_seeds_produce_variation():
    """Verifies that different seeds yield distinct random telemetry samples."""
    t0 = datetime(2026, 8, 30, 14, 0, 0, tzinfo=timezone.utc)
    services = ["auth-service"]

    gen1 = SyntheticIncidentGenerator(seed=1, base_time=t0)
    logs1 = gen1.generate_background_logs(services, t0, duration_minutes=5)

    gen2 = SyntheticIncidentGenerator(seed=999, base_time=t0)
    logs2 = gen2.generate_background_logs(services, t0, duration_minutes=5)

    assert [l.trace_id for l in logs1] != [l.trace_id for l in logs2]


def test_generator_baseline_health():
    """Verifies baseline health records generation."""
    t0 = datetime(2026, 8, 30, 14, 0, 0, tzinfo=timezone.utc)
    services = ["payment-service", "worker-service"]

    gen = SyntheticIncidentGenerator(seed=42, base_time=t0)
    health = gen.generate_baseline_health(services, t0, duration_minutes=10)

    assert len(health) == 10  # 5 time steps (every 2 mins) * 2 services
    for h in health:
        assert h.status.value == "HEALTHY"
        assert h.error_rate_pct < 1.0

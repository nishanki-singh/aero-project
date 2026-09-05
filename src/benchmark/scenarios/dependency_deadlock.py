"""Scenario D: Downstream Dependency Latency & Worker Thread Pool Starvation."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.benchmark.generator import SyntheticIncidentGenerator
from src.schemas.diagnostic import SignalType
from src.schemas.ground_truth import (
    BenchmarkScenarioBundle,
    ExpectedEvidence,
    ExpectedRemediation,
    GroundTruthScenario,
)
from src.schemas.incident import (
    Incident,
    IncidentMetadata,
    IncidentSeverity,
    IncidentStatus,
    TelemetryPayload,
)
from src.schemas.telemetry import (
    DeploymentEvent,
    HealthStatus,
    LogEntry,
    LogLevel,
    MetricPoint,
    MetricSeries,
    ServiceHealth,
)


def generate_dependency_deadlock_scenario(
    seed: int = 42,
    base_time: datetime | None = None,
) -> BenchmarkScenarioBundle:
    """Generates the Dependency Latency & Thread Pool Starvation scenario."""
    gen = SyntheticIncidentGenerator(seed=seed, base_time=base_time)
    t0 = gen.base_time
    service = "checkout-service"
    other_services = ["auth-service", "order-service", "worker-service", "catalog-service"]

    # 1. Background Telemetry
    logs: list[LogEntry] = gen.generate_background_logs(other_services + [service], t0, duration_minutes=25)
    metrics: list[MetricSeries] = []
    health_signals: list[ServiceHealth] = gen.generate_baseline_health(other_services, t0, duration_minutes=25)
    deployments: list[DeploymentEvent] = []

    # 2. Specific Incident Metrics
    # Upstream Dependency Latency Metric
    partner_lat_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 180.0 if m < 4 else (28500.0 + gen.rng.uniform(-1000.0, 1000.0))
        partner_lat_points.append(MetricPoint(timestamp=t, value=round(val, 2)))

    metrics.append(
        MetricSeries(
            metric_name="dependency/partner_payment_latency_p99",
            service_name=service,
            unit="ms",
            points=partner_lat_points,
            labels={"dependency": "partner-payments-api", "target_host": "api.partner-payments.io"},
        )
    )

    # Active Worker Threads (Max capacity: 100)
    thread_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        if m < 4:
            val = 15.0 + gen.rng.uniform(-2.0, 2.0)
        elif m < 8:
            val = 15.0 + (m - 3) * 22.0 + gen.rng.uniform(-1.0, 1.0)
        else:
            val = 100.0  # Max Threads Saturated
        thread_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="server/active_worker_threads",
            service_name=service,
            unit="count",
            points=thread_points,
            labels={"pool": "http-worker-pool", "max_capacity": "100"},
        )
    )

    # CPU Utilization (Drops to near-zero as all threads are blocked waiting for network I/O)
    cpu_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 28.0 if m < 5 else (2.1 + gen.rng.uniform(-0.5, 0.5))
        cpu_points.append(MetricPoint(timestamp=t, value=round(max(0.1, val), 2)))

    metrics.append(
        MetricSeries(
            metric_name="container/cpu_utilization",
            service_name=service,
            unit="percent",
            points=cpu_points,
            labels={"container": "checkout-api"},
        )
    )

    # Injected Incident Logs
    incident_logs = [
        LogEntry(
            timestamp=t0 + timedelta(minutes=4, seconds=45),
            service_name=service,
            log_level=LogLevel.WARN,
            message="Outbound HTTP call to https://api.partner-payments.io/v1/charge exceeding 20000ms for order_id=ord-8819",
            trace_id="trace-dep-001",
            attributes={"dependency": "partner-payments", "latency_ms": 21400},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=6, seconds=30),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="Worker pool starvation: ThreadPoolExecutor queue full (active=100, queue_size=500, rejected=124)",
            trace_id="trace-dep-002",
            attributes={"active_threads": 100, "rejected_requests": 124},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=8, seconds=15),
            service_name=service,
            log_level=LogLevel.FATAL,
            message="Health probe failed: GET /healthz timed out after 5000ms (worker thread pool unresponsive)",
            trace_id="trace-dep-003",
            attributes={"probe": "livenessProbe"},
        ),
    ]
    logs.extend(incident_logs)
    logs.sort(key=lambda x: x.timestamp)

    # Health Checks
    for m in range(0, 25, 2):
        t = t0 + timedelta(minutes=m)
        if m < 6:
            status = HealthStatus.HEALTHY
            lat = gen.rng.uniform(30.0, 45.0)
            err = 0.0
            det = "Healthy"
        elif m < 8:
            status = HealthStatus.DEGRADED
            lat = gen.rng.uniform(5000.0, 15000.0)
            err = 20.0
            det = "High checkout latency"
        else:
            status = HealthStatus.UNHEALTHY
            lat = 30000.0
            err = 95.0
            det = "Thread pool starvation (Health check timeout)"
        health_signals.append(
            ServiceHealth(
                timestamp=t,
                service_name=service,
                status=status,
                latency_p99_ms=round(lat, 2),
                error_rate_pct=round(err, 2),
                details=det,
            )
        )
    health_signals.sort(key=lambda x: x.timestamp)

    # Ground Truth
    ground_truth = GroundTruthScenario(
        scenario_id="BENCHMARK-DEP-004",
        scenario_name="Checkout Service Thread Pool Starvation via Upstream Dependency Latency",
        category="DEPENDENCY_OUTAGE_TIMEOUT",
        affected_service=service,
        trigger_event="Third-party payment partner API (api.partner-payments.io) experienced latency degradation (>28s).",
        root_cause_summary=(
            "Third-party payment gateway degraded to 28s response times. Because checkout-service lacked client-side socket timeouts "
            "and circuit breakers, all 100 worker threads blocked waiting for HTTP responses, causing complete thread pool starvation and unresponsive health checks."
        ),
        expected_root_cause_category="DEPENDENCY_OUTAGE_TIMEOUT",
        expected_evidence_signals=[
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="dependency/partner_payment_latency_p99",
                description="Upstream partner latency metric spiking to >28,000ms.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="server/active_worker_threads",
                description="Active worker thread count hitting 100% capacity while CPU is near 0%.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="Worker pool starvation",
                description="ThreadPoolExecutor queue exhaustion log.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="api.partner-payments.io",
                description="Outbound log identifying partner payment gateway as the bottleneck.",
                is_mandatory=True,
            ),
        ],
        expected_remediation=ExpectedRemediation(
            key_actions=[
                "Configure 2500ms socket timeout and circuit breaker for partner-payments client",
                "Enable asynchronous fallback payment queue (degraded checkout mode)",
                "Restart checkout-service pods to reclaim blocked worker threads",
            ],
            expected_verification_metric="Verify server/active_worker_threads drops below 30 and P99 latency returns under 200ms.",
        ),
        expected_diagnostic_conclusion=(
            "Diagnose checkout-service failure as Downstream Dependency Latency causing Thread Pool Starvation due to missing client timeouts."
        ),
        evaluation_criteria={
            "weight_root_cause": 0.4,
            "weight_evidence_citation": 0.4,
            "weight_remediation": 0.2,
        },
    )

    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-DEP",
            title="Checkout Service Complete Freeze: Thread Pool Deadlock",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service=service,
            impact_summary="100% of customer checkouts hanging and timing out due to upstream payment partner latency.",
            detected_at=t0 + timedelta(minutes=7),
        ),
        telemetry=TelemetryPayload(
            time_window_start=t0,
            time_window_end=t0 + timedelta(minutes=25),
            logs=logs,
            metrics=metrics,
            deployments=deployments,
            health_signals=health_signals,
        ),
    )

    return BenchmarkScenarioBundle(ground_truth=ground_truth, incident=incident)

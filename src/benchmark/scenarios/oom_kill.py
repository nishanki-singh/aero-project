"""Scenario A: Memory Leak & Container OOMKill Cascade."""

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


def generate_oom_kill_scenario(
    seed: int = 42,
    base_time: datetime | None = None,
) -> BenchmarkScenarioBundle:
    """Generates the OOMKill scenario with correlated logs, metrics, health signals, and ground truth."""
    gen = SyntheticIncidentGenerator(seed=seed, base_time=base_time)
    t0 = gen.base_time
    service = "worker-service"
    other_services = ["auth-service", "order-service", "payment-service", "catalog-service"]

    # 1. Background Telemetry
    logs: list[LogEntry] = gen.generate_background_logs(other_services + [service], t0, duration_minutes=25)
    metrics: list[MetricSeries] = []
    health_signals: list[ServiceHealth] = gen.generate_baseline_health(other_services, t0, duration_minutes=25)
    deployments: list[DeploymentEvent] = [
        DeploymentEvent(
            timestamp=t0 - timedelta(minutes=45),
            service_name=service,
            version="v1.9.0",
            commit_hash="c3a81f2",
            deployed_by="ci-deploy-bot",
            change_summary="Update batch processing worker queue consumer to use concurrent workers",
            environment="production",
        )
    ]

    # 2. Specific Incident Telemetry Progression
    # Memory Ramp Metric
    memory_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        if m < 5:
            val = 32.0 + gen.rng.uniform(-1.0, 1.0)
        elif m < 13:
            val = 32.0 + (m - 5) * 8.5 + gen.rng.uniform(-0.5, 0.5)
        elif m == 13:
            val = 99.8
        else:
            val = 0.0  # Container killed / down
        memory_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="container/memory_utilization",
            service_name=service,
            unit="percent",
            points=memory_points,
            labels={"pod": "worker-service-7f4c", "container": "worker"},
        )
    )

    # HTTP 502 Error Rate Metric
    error_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 0.0 if m < 13 else (94.5 + gen.rng.uniform(-2.0, 2.0))
        error_points.append(MetricPoint(timestamp=t, value=round(val, 2)))

    metrics.append(
        MetricSeries(
            metric_name="http/server/error_rate",
            service_name=service,
            unit="percent",
            points=error_points,
            labels={"status_code": "502"},
        )
    )

    # Injected Specific Error Logs
    incident_logs = [
        LogEntry(
            timestamp=t0 + timedelta(minutes=5, seconds=12),
            service_name=service,
            log_level=LogLevel.INFO,
            message="Batch ingest trigger: Received uncompressed batch payload (payload_size_mb=850.4)",
            trace_id="trace-oom-001",
            attributes={"batch_id": "batch-9920", "worker_thread": "pool-3-thread-1"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=7, seconds=45),
            service_name=service,
            log_level=LogLevel.WARN,
            message="Heap usage exceeds 75% threshold (1536MB / 2048MB). Initiating GC sweep.",
            trace_id="trace-oom-001",
            attributes={"heap_used_mb": 1536, "heap_max_mb": 2048},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=10, seconds=30),
            service_name=service,
            log_level=LogLevel.WARN,
            message="GC overhead limit exceeded. Spent 89.2% CPU time in FullGC pause.",
            trace_id="trace-oom-001",
            attributes={"gc_pause_ms": 1420},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=13, seconds=2),
            service_name=service,
            log_level=LogLevel.FATAL,
            message="java.lang.OutOfMemoryError: Java heap space at com.aero.worker.BatchProcessor.bufferAll(BatchProcessor.java:184)",
            trace_id="trace-oom-001",
            attributes={"error_class": "OutOfMemoryError"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=13, seconds=5),
            service_name=service,
            log_level=LogLevel.FATAL,
            message="Container worker-service-7f4c terminated by kernel with ExitCode 137 (OOMKilled)",
            trace_id="trace-oom-001",
            attributes={"exit_code": 137, "reason": "OOMKilled"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=14, seconds=10),
            service_name="api-gateway",
            log_level=LogLevel.ERROR,
            message="Upstream gateway received HTTP 502 Bad Gateway: connection refused to worker-service:8080",
            trace_id="trace-oom-002",
            attributes={"upstream": "worker-service:8080", "status_code": 502},
        ),
    ]
    logs.extend(incident_logs)
    logs.sort(key=lambda x: x.timestamp)

    # Injected Specific Health Checks
    for m in range(0, 25, 2):
        t = t0 + timedelta(minutes=m)
        if m < 8:
            status = HealthStatus.HEALTHY
            lat = gen.rng.uniform(20.0, 30.0)
            err = 0.0
            det = "Healthy"
        elif m < 13:
            status = HealthStatus.DEGRADED
            lat = gen.rng.uniform(300.0, 800.0)
            err = 5.0
            det = "High GC latency detected"
        else:
            status = HealthStatus.UNHEALTHY
            lat = 5000.0
            err = 95.0
            det = "Service unavailable (Connection refused / OOMKilled)"
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

    # 3. Ground Truth Specification
    ground_truth = GroundTruthScenario(
        scenario_id="BENCHMARK-OOM-001",
        scenario_name="Worker Service Memory Leak & Container OOMKill",
        category="RESOURCE_EXHAUSTION_MEMORY",
        affected_service=service,
        trigger_event="Batch job received large uncompressed payload (850MB) triggering unbounded in-memory buffering.",
        root_cause_summary=(
            "Worker service experienced unbounded memory allocation during batch payload ingestion, "
            "leading to FullGC pauses and kernel termination via ExitCode 137 (OOMKilled), causing cascading 502 errors."
        ),
        expected_root_cause_category="RESOURCE_EXHAUSTION_MEMORY",
        expected_evidence_signals=[
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="container/memory_utilization",
                description="Memory utilization ramping from 32% to ~100% over minutes 5 to 13.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="ExitCode 137",
                description="Container kernel termination log citing ExitCode 137 / OOMKilled.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="OutOfMemoryError",
                description="Java heap space OutOfMemoryError stack trace.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.HEALTH,
                pattern="UNHEALTHY",
                description="Service health transitioning to UNHEALTHY following OOMKill.",
                is_mandatory=False,
            ),
        ],
        expected_remediation=ExpectedRemediation(
            key_actions=[
                "Restart worker-service container / deployment to clear hung pods",
                "Increase container memory limit from 2Gi to 4Gi in Cloud Run/Kubernetes manifest",
                "Enable chunked streaming parser for batch payloads to prevent buffering entire payloads into RAM",
            ],
            expected_verification_metric="Verify container/memory_utilization stabilizes under 60% and HTTP 502 error rate drops to 0%.",
        ),
        expected_diagnostic_conclusion=(
            "Diagnose worker-service failure as Memory Exhaustion / OOMKill (ExitCode 137) triggered by batch ingestion."
        ),
        evaluation_criteria={
            "weight_root_cause": 0.4,
            "weight_evidence_citation": 0.4,
            "weight_remediation": 0.2,
        },
    )

    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-OOM",
            title="Worker Service 502 Outage: Container OOMKilled",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service=service,
            impact_summary="Batch processing pipeline halted; API gateway returning HTTP 502 for all asynchronous tasks.",
            detected_at=t0 + timedelta(minutes=13),
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

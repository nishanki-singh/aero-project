"""Scenario B: Database Connection Pool Exhaustion via Unindexed Query."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

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


def generate_db_pool_exhaustion_scenario(
    seed: int = 42,
    base_time: Optional[datetime] = None,
) -> BenchmarkScenarioBundle:
    """Generates the Database Connection Pool Exhaustion scenario."""
    gen = SyntheticIncidentGenerator(seed=seed, base_time=base_time)
    t0 = gen.base_time
    service = "order-service"
    other_services = ["auth-service", "worker-service", "payment-service", "catalog-service"]

    # 1. Background Telemetry
    logs: List[LogEntry] = gen.generate_background_logs(other_services + [service], t0, duration_minutes=25)
    metrics: List[MetricSeries] = []
    health_signals: List[ServiceHealth] = gen.generate_baseline_health(other_services, t0, duration_minutes=25)

    # 2. Deployment Event
    deploy_time = t0 + timedelta(minutes=3)
    deployments: List[DeploymentEvent] = [
        DeploymentEvent(
            timestamp=deploy_time,
            service_name=service,
            version="v2.4.1",
            commit_hash="8e4a90b",
            deployed_by="release-pipeline",
            change_summary="Add order status filtering query in checkout workflow",
            environment="production",
        )
    ]

    # 3. Specific Metrics
    # Active DB Connections Metric (Max pool size: 20)
    db_conn_points: List[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        if m < 4:
            val = 4.0 + gen.rng.uniform(-1.0, 1.0)
        elif m < 8:
            val = 4.0 + (m - 3) * 4.0 + gen.rng.uniform(-0.5, 0.5)
        else:
            val = 20.0  # Max Pool Saturated
        db_conn_points.append(MetricPoint(timestamp=t, value=round(min(20.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="database/pool/active_connections",
            service_name=service,
            unit="count",
            points=db_conn_points,
            labels={"pool": "HikariPool-1", "max_capacity": "20"},
        )
    )

    # HTTP 504 Error Rate
    error_points: List[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 0.0 if m < 6 else (96.0 + gen.rng.uniform(-2.0, 2.0))
        error_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="http/server/error_rate",
            service_name=service,
            unit="percent",
            points=error_points,
            labels={"status_code": "504"},
        )
    )

    # Injected Incident Logs
    incident_logs = [
        LogEntry(
            timestamp=deploy_time + timedelta(seconds=15),
            service_name=service,
            log_level=LogLevel.INFO,
            message="Deployment rollout completed for order-service:v2.4.1 across 4 replicas",
            trace_id="deploy-trace-01",
            attributes={"version": "v2.4.1"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=5, seconds=20),
            service_name=service,
            log_level=LogLevel.WARN,
            message="Slow query detected: SELECT * FROM orders WHERE status = ? AND customer_id = ? (execution_time=12400ms, scan_type=Seq Scan)",
            trace_id="trace-db-001",
            attributes={"query_duration_ms": 12400, "table": "orders"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=7, seconds=45),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="HikariPool-1 - Connection is not available, request timed out after 30000ms (total=20, active=20, idle=0, waiting=48)",
            trace_id="trace-db-002",
            attributes={"pool_active": 20, "pool_max": 20, "waiting_threads": 48},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=9, seconds=10),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="HTTP 504 Gateway Timeout on POST /api/v1/orders/checkout: database connection acquisition timed out",
            trace_id="trace-db-003",
            attributes={"status_code": 504, "endpoint": "/api/v1/orders/checkout"},
        ),
    ]
    logs.extend(incident_logs)
    logs.sort(key=lambda x: x.timestamp)

    # Health Checks
    for m in range(0, 25, 2):
        t = t0 + timedelta(minutes=m)
        if m < 6:
            status = HealthStatus.HEALTHY
            lat = gen.rng.uniform(25.0, 35.0)
            err = 0.0
            det = "Healthy"
        elif m < 8:
            status = HealthStatus.DEGRADED
            lat = gen.rng.uniform(400.0, 1200.0)
            err = 15.0
            det = "Slow response times"
        else:
            status = HealthStatus.UNHEALTHY
            lat = 15000.0
            err = 98.0
            det = "Connection pool exhaustion (HikariCP timeout)"
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
        scenario_id="BENCHMARK-DB-002",
        scenario_name="Order Service Database Connection Pool Starvation",
        category="DATABASE_CONNECTION_EXHAUSTION",
        affected_service=service,
        trigger_event="Deployment of order-service:v2.4.1 containing an unindexed query in checkout workflow.",
        root_cause_summary=(
            "Release v2.4.1 introduced a slow unindexed database query (sequential scan on orders table taking >12s), "
            "exhausting the HikariCP connection pool (20/20 active) and causing subsequent checkout requests to fail with HTTP 504 timeouts."
        ),
        expected_root_cause_category="DATABASE_CONNECTION_EXHAUSTION",
        expected_evidence_signals=[
            ExpectedEvidence(
                signal_type=SignalType.DEPLOYMENT,
                pattern="v2.4.1",
                description="Deployment event of order-service:v2.4.1 preceding the pool saturation.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="database/pool/active_connections",
                description="Active DB connections reaching max capacity (20/20).",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="HikariPool-1 - Connection is not available",
                description="ConnectionTimeoutException log from database connection pool.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="Slow query detected",
                description="Slow SQL query log citing sequential scan on orders table.",
                is_mandatory=False,
            ),
        ],
        expected_remediation=ExpectedRemediation(
            key_actions=[
                "Rollback order-service to previous stable release v2.4.0",
                "Add database index on orders (status, customer_id)",
                "Temporarily increase HikariCP maximum pool size from 20 to 40",
            ],
            expected_verification_metric="Verify database/pool/active_connections drops below 10 and HTTP 504 error rate drops to 0%.",
        ),
        expected_diagnostic_conclusion=(
            "Diagnose order-service failure as Database Connection Pool Starvation caused by unindexed query introduced in v2.4.1 deployment."
        ),
        evaluation_criteria={
            "weight_root_cause": 0.4,
            "weight_evidence_citation": 0.4,
            "weight_remediation": 0.2,
        },
    )

    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-DB",
            title="Order Service 504 Outage: DB Connection Pool Exhaustion",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service=service,
            impact_summary="Checkout transactions failing for 96% of customers due to database pool starvation.",
            detected_at=t0 + timedelta(minutes=8),
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

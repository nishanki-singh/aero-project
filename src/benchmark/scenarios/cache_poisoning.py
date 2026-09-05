"""Scenario E: Cache Stampede / Cache Key Corruption."""

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


def generate_cache_poisoning_scenario(
    seed: int = 42,
    base_time: datetime | None = None,
) -> BenchmarkScenarioBundle:
    """Generates the Cache Stampede / Cache Key Corruption scenario."""
    gen = SyntheticIncidentGenerator(seed=seed, base_time=base_time)
    t0 = gen.base_time
    service = "catalog-service"
    other_services = ["auth-service", "order-service", "worker-service", "payment-service"]

    # 1. Background Telemetry
    logs: list[LogEntry] = gen.generate_background_logs(other_services + [service], t0, duration_minutes=25)
    metrics: list[MetricSeries] = []
    health_signals: list[ServiceHealth] = gen.generate_baseline_health(other_services, t0, duration_minutes=25)

    # 2. Deployment Event
    deploy_time = t0 + timedelta(minutes=2)
    deployments: list[DeploymentEvent] = [
        DeploymentEvent(
            timestamp=deploy_time,
            service_name=service,
            version="v3.1.0",
            commit_hash="d7e21a8",
            deployed_by="release-pipeline",
            change_summary="Migrate Redis cache serializer to snappy compressed binary format",
            environment="production",
        )
    ]

    # 3. Specific Metrics
    # Redis Cache Hit Ratio Metric (Collapses from 98.5% to 1.8%)
    cache_hit_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 98.5 if m < 3 else (1.8 + gen.rng.uniform(-0.5, 0.5))
        cache_hit_points.append(MetricPoint(timestamp=t, value=round(max(0.0, val), 2)))

    metrics.append(
        MetricSeries(
            metric_name="redis/cache_hit_ratio",
            service_name=service,
            unit="percent",
            points=cache_hit_points,
            labels={"cache_tier": "redis-cluster", "cluster": "catalog-cache"},
        )
    )

    # Database CPU Utilization (Spikes to 100% due to cache stampede)
    db_cpu_points: list[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        if m < 3:
            val = 18.0 + gen.rng.uniform(-2.0, 2.0)
        elif m < 6:
            val = 18.0 + (m - 2) * 26.0 + gen.rng.uniform(-1.0, 1.0)
        else:
            val = 100.0  # 100% Database Saturation
        db_cpu_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="database/cpu_utilization",
            service_name=service,
            unit="percent",
            points=db_cpu_points,
            labels={"db_instance": "catalog-postgres-primary"},
        )
    )

    # Injected Incident Logs
    incident_logs = [
        LogEntry(
            timestamp=deploy_time + timedelta(seconds=20),
            service_name=service,
            log_level=LogLevel.INFO,
            message="catalog-service:v3.1.0 active - updated Redis serializer to SnappyBinaryCodec",
            trace_id="deploy-trace-02",
            attributes={"version": "v3.1.0"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=3, seconds=15),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="SerializationError: Corrupted byte header for Redis key prefix 'catalog:v2' - failed to deserialize cached object, falling back to database query",
            trace_id="trace-cache-001",
            attributes={"codec": "SnappyBinaryCodec", "cache_key": "catalog:v2:category:electronics"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=4, seconds=45),
            service_name=service,
            log_level=LogLevel.WARN,
            message="Cache stampede warning: Cache hit ratio dropped to 1.8%. Database read IOPS surging to 14,200 IOPS",
            trace_id="trace-cache-002",
            attributes={"cache_miss_rate": 98.2, "db_iops": 14200},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=6, seconds=30),
            service_name=service,
            log_level=LogLevel.FATAL,
            message="PostgreSQL primary CPU saturated at 100.0%: query queue depth exceeded maximum limit (queue_depth=840)",
            trace_id="trace-cache-003",
            attributes={"cpu_percent": 100.0, "db_status": "SATURATED"},
        ),
    ]
    logs.extend(incident_logs)
    logs.sort(key=lambda x: x.timestamp)

    # Health Checks
    for m in range(0, 25, 2):
        t = t0 + timedelta(minutes=m)
        if m < 4:
            status = HealthStatus.HEALTHY
            lat = gen.rng.uniform(15.0, 25.0)
            err = 0.0
            det = "Healthy"
        elif m < 6:
            status = HealthStatus.DEGRADED
            lat = gen.rng.uniform(500.0, 1500.0)
            err = 10.0
            det = "Cache miss storm / Elevated latency"
        else:
            status = HealthStatus.UNHEALTHY
            lat = 8500.0
            err = 85.0
            det = "Database CPU 100% / Request timeouts"
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
        scenario_id="BENCHMARK-CACHE-005",
        scenario_name="Catalog Service Cache Stampede / Cache Key Corruption",
        category="CACHE_STAMPEDE_SERIALIZATION",
        affected_service=service,
        trigger_event="Deployment of catalog-service:v3.1.0 with incompatible Snappy binary cache serializer.",
        root_cause_summary=(
            "Release v3.1.0 introduced an incompatible Redis serialization format (SnappyBinaryCodec) that failed to deserialize "
            "existing cache keys. This triggered a total cache hit ratio collapse (98% -> 1.8%) and caused an unmitigated cache stampede "
            "onto the primary PostgreSQL database, driving DB CPU to 100%."
        ),
        expected_root_cause_category="CACHE_STAMPEDE_SERIALIZATION",
        expected_evidence_signals=[
            ExpectedEvidence(
                signal_type=SignalType.DEPLOYMENT,
                pattern="v3.1.0",
                description="Deployment event of catalog-service:v3.1.0 changing cache serializer.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="SerializationError",
                description="Redis serialization/deserialization failure log.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="redis/cache_hit_ratio",
                description="Cache hit ratio collapse metric (98% -> 1.8%).",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="database/cpu_utilization",
                description="Database CPU reaching 100% under cache stampede.",
                is_mandatory=True,
            ),
        ],
        expected_remediation=ExpectedRemediation(
            key_actions=[
                "Rollback catalog-service to previous release v3.0.9",
                "Flush corrupted Redis keys with prefix 'catalog:v2' using selective key purge",
                "Implement mutex/singleflight locking on cache misses to prevent raw cache stampedes",
            ],
            expected_verification_metric="Verify redis/cache_hit_ratio recovers above 95% and database/cpu_utilization drops below 30%.",
        ),
        expected_diagnostic_conclusion=(
            "Diagnose catalog-service outage as Cache Stampede / Cache Key Corruption caused by incompatible cache serializer in v3.1.0."
        ),
        evaluation_criteria={
            "weight_root_cause": 0.4,
            "weight_evidence_citation": 0.4,
            "weight_remediation": 0.2,
        },
    )

    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-CACHE",
            title="Catalog Service Outage: Cache Key Deserialization & DB Stampede",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service=service,
            impact_summary="Catalog browsing and search completely unresponsive due to database CPU saturation following cache failure.",
            detected_at=t0 + timedelta(minutes=5),
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

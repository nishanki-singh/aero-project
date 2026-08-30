"""Scenario C: Configuration Drift & Secret/Endpoint Mismatch."""

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


def generate_config_drift_scenario(
    seed: int = 42,
    base_time: Optional[datetime] = None,
) -> BenchmarkScenarioBundle:
    """Generates the Configuration Drift scenario."""
    gen = SyntheticIncidentGenerator(seed=seed, base_time=base_time)
    t0 = gen.base_time
    service = "auth-service"
    other_services = ["order-service", "worker-service", "payment-service", "catalog-service"]

    # 1. Background Telemetry
    logs: List[LogEntry] = gen.generate_background_logs(other_services + [service], t0, duration_minutes=25)
    metrics: List[MetricSeries] = []
    health_signals: List[ServiceHealth] = gen.generate_baseline_health(other_services, t0, duration_minutes=25)

    # 2. Deployment / Config Event
    config_time = t0 + timedelta(minutes=2)
    deployments: List[DeploymentEvent] = [
        DeploymentEvent(
            timestamp=config_time,
            service_name=service,
            version="config-rev-42",
            commit_hash="f4d92a1",
            deployed_by="terraform-cloud",
            change_summary="Update auth-service ConfigMap: switch JWKS public key resolver endpoint",
            environment="production",
        )
    ]

    # 3. Specific Metrics
    # JWT Failure Rate Metric
    jwt_fail_points: List[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 0.02 if m < 3 else (99.2 + gen.rng.uniform(-0.5, 0.5))
        jwt_fail_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="auth/jwt_verification_failure_rate",
            service_name=service,
            unit="percent",
            points=jwt_fail_points,
            labels={"auth_mechanism": "JWKS_OIDC"},
        )
    )

    # HTTP 401 Error Rate Metric
    http_401_points: List[MetricPoint] = []
    for m in range(25):
        t = t0 + timedelta(minutes=m)
        val = 0.05 if m < 3 else (97.8 + gen.rng.uniform(-1.0, 1.0))
        http_401_points.append(MetricPoint(timestamp=t, value=round(min(100.0, max(0.0, val)), 2)))

    metrics.append(
        MetricSeries(
            metric_name="http/server/error_rate",
            service_name=service,
            unit="percent",
            points=http_401_points,
            labels={"status_code": "401"},
        )
    )

    # Injected Incident Logs
    incident_logs = [
        LogEntry(
            timestamp=config_time + timedelta(seconds=10),
            service_name=service,
            log_level=LogLevel.INFO,
            message="ConfigMap reload applied: JWKS_ENDPOINT_URI='https://auth-internal.prod.local/keys'",
            trace_id="config-reload-01",
            attributes={"config_version": "rev-42"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=3, seconds=15),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="JWTValidationException: Failed to resolve JWKS endpoint (java.net.UnknownHostException: auth-internal.prod.local)",
            trace_id="trace-auth-001",
            attributes={"error_class": "UnknownHostException", "target_host": "auth-internal.prod.local"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=4, seconds=5),
            service_name=service,
            log_level=LogLevel.WARN,
            message="Token signature validation failed: Public key not found in key cache for kid=key-2026-a",
            trace_id="trace-auth-002",
            attributes={"key_id": "key-2026-a"},
        ),
        LogEntry(
            timestamp=t0 + timedelta(minutes=5, seconds=30),
            service_name=service,
            log_level=LogLevel.ERROR,
            message="HTTP 401 Unauthorized: Invalid bearer token presented on POST /api/v1/auth/verify",
            trace_id="trace-auth-003",
            attributes={"status_code": 401},
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
        else:
            status = HealthStatus.UNHEALTHY
            lat = gen.rng.uniform(30.0, 50.0)
            err = 98.0
            det = "Authentication verification failure (401 rate >95%)"
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
        scenario_id="BENCHMARK-CFG-003",
        scenario_name="Auth Service Configuration Drift & JWKS URL Mismatch",
        category="CONFIGURATION_DRIFT",
        affected_service=service,
        trigger_event="ConfigMap update (config-rev-42) configured unresolvable JWKS endpoint URI.",
        root_cause_summary=(
            "ConfigMap revision rev-42 misconfigured the JWKS endpoint URI to an unresolvable hostname (auth-internal.prod.local), "
            "causing java.net.UnknownHostException during JWT key fetch and resulting in 98% HTTP 401 authentication rejection."
        ),
        expected_root_cause_category="CONFIGURATION_DRIFT",
        expected_evidence_signals=[
            ExpectedEvidence(
                signal_type=SignalType.DEPLOYMENT,
                pattern="config-rev-42",
                description="ConfigMap update event deploying revision rev-42.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="UnknownHostException",
                description="DNS resolution failure log citing auth-internal.prod.local.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.LOG,
                pattern="JWTValidationException",
                description="JWT validation exception log citing key resolution failure.",
                is_mandatory=True,
            ),
            ExpectedEvidence(
                signal_type=SignalType.METRIC,
                pattern="auth/jwt_verification_failure_rate",
                description="Failure rate metric spiking to >99%.",
                is_mandatory=True,
            ),
        ],
        expected_remediation=ExpectedRemediation(
            key_actions=[
                "Rollback auth-service ConfigMap to previous revision rev-41",
                "Correct the JWKS endpoint URI to https://auth.internal.production/keys",
                "Send SIGHUP / trigger dynamic configuration reload on auth-service pods",
            ],
            expected_verification_metric="Verify auth/jwt_verification_failure_rate drops to 0% and HTTP 401 error rate returns to normal baseline.",
        ),
        expected_diagnostic_conclusion=(
            "Diagnose auth-service outage as Configuration Drift (invalid JWKS URI hostname in ConfigMap rev-42) causing JWT authentication collapse."
        ),
        evaluation_criteria={
            "weight_root_cause": 0.4,
            "weight_evidence_citation": 0.4,
            "weight_remediation": 0.2,
        },
    )

    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-CFG",
            title="Auth Service Global 401 Outage: ConfigMap Drift",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service=service,
            impact_summary="Users globally unable to authenticate; all microservice API calls rejected with 401 Unauthorized.",
            detected_at=t0 + timedelta(minutes=4),
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

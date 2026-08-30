"""Unit tests for AERO Pydantic schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.schemas.diagnostic import (
    AeroDiagnosticReport,
    ConfidenceLevel,
    ConfidenceRating,
    HistoricalIncidentMatch,
    ProbableRootCause,
    RecommendedRemediation,
    RunbookReference,
    SignalType,
    SupportingEvidence,
)
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


def test_log_entry_schema():
    """Tests LogEntry serialization and validation."""
    now = datetime.now(timezone.utc)
    entry = LogEntry(
        timestamp=now,
        service_name="payment-service",
        log_level=LogLevel.ERROR,
        message="Database connection failed",
        trace_id="trace-12345",
        attributes={"db_host": "db.prod.internal", "retry_count": 3},
    )
    assert entry.service_name == "payment-service"
    assert entry.log_level == LogLevel.ERROR
    assert entry.attributes["retry_count"] == 3

    # Test JSON round-trip
    dumped = entry.model_dump_json()
    loaded = LogEntry.model_validate_json(dumped)
    assert loaded.message == entry.message
    assert loaded.trace_id == "trace-12345"


def test_metric_series_schema():
    """Tests MetricSeries and MetricPoint models."""
    now = datetime.now(timezone.utc)
    series = MetricSeries(
        metric_name="container/memory_utilization",
        service_name="worker-service",
        unit="percent",
        points=[MetricPoint(timestamp=now, value=88.5)],
        labels={"pod": "worker-1"},
    )
    assert len(series.points) == 1
    assert series.points[0].value == 88.5
    assert series.unit == "percent"


def test_deployment_event_schema():
    """Tests DeploymentEvent validation."""
    now = datetime.now(timezone.utc)
    event = DeploymentEvent(
        timestamp=now,
        service_name="order-service",
        version="v2.4.1",
        commit_hash="a1b2c3d",
        deployed_by="ci-bot",
        change_summary="Add index to order table",
        environment="production",
    )
    assert event.version == "v2.4.1"
    assert event.environment == "production"


def test_service_health_schema():
    """Tests ServiceHealth validation."""
    now = datetime.now(timezone.utc)
    health = ServiceHealth(
        timestamp=now,
        service_name="auth-service",
        status=HealthStatus.DEGRADED,
        latency_p99_ms=450.0,
        error_rate_pct=12.5,
        details="Intermittent 503 errors",
    )
    assert health.status == HealthStatus.DEGRADED
    assert health.latency_p99_ms == 450.0


def test_incident_bundle_schema():
    """Tests complete Incident and TelemetryPayload model nesting."""
    now = datetime.now(timezone.utc)
    incident = Incident(
        metadata=IncidentMetadata(
            incident_id="INC-20260830-TEST",
            title="Test Incident",
            severity=IncidentSeverity.SEV1_CRITICAL,
            status=IncidentStatus.INVESTIGATING,
            affected_service="payment-service",
            impact_summary="Payment gateway returning 500 errors",
            detected_at=now,
        ),
        telemetry=TelemetryPayload(
            time_window_start=now,
            time_window_end=now,
            logs=[
                LogEntry(
                    timestamp=now,
                    service_name="payment-service",
                    log_level=LogLevel.FATAL,
                    message="Fatal deadlock",
                )
            ],
            metrics=[],
            deployments=[],
            health_signals=[],
        ),
    )
    assert incident.metadata.severity == IncidentSeverity.SEV1_CRITICAL
    assert len(incident.telemetry.logs) == 1

    json_str = incident.model_dump_json()
    reloaded = Incident.model_validate_json(json_str)
    assert reloaded.metadata.incident_id == "INC-20260830-TEST"


def test_diagnostic_report_schema():
    """Tests AeroDiagnosticReport schema structure and confidence rating boundaries."""
    now = datetime.now(timezone.utc)
    report = AeroDiagnosticReport(
        incident_id="INC-20260830-001",
        service_name="payment-service",
        severity="CRITICAL",
        incident_summary="Payment failure due to DB pool exhaustion",
        probable_root_cause=ProbableRootCause(
            title="DB Connection Starvation",
            description="Long running transactions exhausted pool",
            category="DATABASE_CONNECTION_EXHAUSTION",
            trigger_event="v2.4.1 deploy",
        ),
        confidence_level=ConfidenceLevel(
            score=0.92,
            rating=ConfidenceRating.HIGH,
            rationale="Exact correlation between logs and metrics",
        ),
        supporting_evidence=[
            SupportingEvidence(
                signal_type=SignalType.LOG,
                timestamp=now,
                source="payment-pod",
                content="HikariPool connection timeout",
            )
        ],
        similar_historical_incidents=[
            HistoricalIncidentMatch(
                incident_id="INC-2025-01",
                title="Previous DB pool outage",
                similarity_score=0.88,
                resolution_summary="Scaled pool size",
            )
        ],
        recommended_remediation=RecommendedRemediation(
            immediate_steps=["Rollback release", "Scale DB"],
            dry_run_command="gcloud run update --dry-run",
            verification_metric="active_connections < 10",
            rollback_plan="Revert to v2.4.0",
        ),
        relevant_runbook=RunbookReference(
            title="Database Triage Runbook",
            document_uri="gs://aero-runbooks/db-triage.md",
            pertinent_section="Section 4.1",
        ),
    )
    assert report.confidence_level.rating == ConfidenceRating.HIGH
    assert report.confidence_level.score == 0.92

    # Verify score out of bounds raises ValidationError
    with pytest.raises(ValidationError):
        ConfidenceLevel(
            score=1.5,
            rating=ConfidenceRating.HIGH,
            rationale="Invalid score",
        )

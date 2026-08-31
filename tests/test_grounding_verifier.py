"""Unit tests for the deterministic grounding verifier and hallucination guardrails."""

from datetime import datetime, timedelta, timezone
from src.benchmark.scenarios.db_pool_exhaustion import generate_db_pool_exhaustion_scenario
from src.engine.grounding_verifier import GroundingVerifier
from src.schemas.diagnostic import (
    AeroDiagnosticReport,
    ConfidenceLevel,
    ConfidenceRating,
    ProbableRootCause,
    RecommendedRemediation,
    SignalType,
    SupportingEvidence,
)


def test_grounding_verifier_passes_on_valid_evidence():
    """Verifies that genuine telemetry citations are verified with 0% hallucination rate."""
    bundle = generate_db_pool_exhaustion_scenario(seed=42)
    incident = bundle.incident
    t0 = incident.telemetry.time_window_start

    # Build report with authentic citations from the incident
    report = AeroDiagnosticReport(
        incident_id=incident.metadata.incident_id,
        service_name="order-service",
        severity="CRITICAL",
        incident_summary="DB pool starved",
        probable_root_cause=ProbableRootCause(
            title="DB Pool Exhaustion",
            description="Connections exhausted",
            category="DATABASE_CONNECTION_EXHAUSTION",
        ),
        confidence_level=ConfidenceLevel(score=0.95, rating=ConfidenceRating.HIGH, rationale="Correlated"),
        supporting_evidence=[
            SupportingEvidence(
                signal_type=SignalType.METRIC,
                timestamp=t0,
                source="database/pool/active_connections",
                content="Active DB connections spiked to 20.",
            ),
            SupportingEvidence(
                signal_type=SignalType.DEPLOYMENT,
                timestamp=t0 + timedelta(minutes=3),
                source="order-service",
                content="Deployed version v2.4.1",
            ),
        ],
        recommended_remediation=RecommendedRemediation(
            immediate_steps=["Rollback release"],
            verification_metric="active_connections < 10",
            rollback_plan="Revert to v2.4.0",
        ),
    )

    result = GroundingVerifier.verify(report, incident)
    assert result.is_fully_grounded is True
    assert result.hallucination_rate == 0.0
    assert result.grounding_precision == 1.0
    assert result.verified_count == 2
    assert result.unverified_count == 0


def test_grounding_verifier_catches_hallucinations():
    """Verifies that fabricated logs, non-existent metrics, and bogus deployments are flagged as hallucinations."""
    bundle = generate_db_pool_exhaustion_scenario(seed=42)
    incident = bundle.incident
    t0 = incident.telemetry.time_window_start

    # Build report with hallucinated / fabricated evidence
    report = AeroDiagnosticReport(
        incident_id=incident.metadata.incident_id,
        service_name="order-service",
        severity="CRITICAL",
        incident_summary="Fabricated incident",
        probable_root_cause=ProbableRootCause(
            title="Fake Root Cause",
            description="Fake description",
            category="DATABASE_CONNECTION_EXHAUSTION",
        ),
        confidence_level=ConfidenceLevel(score=0.5, rating=ConfidenceRating.LOW, rationale="Fake"),
        supporting_evidence=[
            SupportingEvidence(
                signal_type=SignalType.LOG,
                timestamp=t0 + timedelta(hours=50),  # Wrong timestamp
                source="fake-service",
                content="FatalNullPointerExceptionInNonExistentCode",
            ),
            SupportingEvidence(
                signal_type=SignalType.METRIC,
                timestamp=t0,
                source="non_existent/fake_metric_name",
                content="Fake metric reached 9999",
            ),
            SupportingEvidence(
                signal_type=SignalType.DEPLOYMENT,
                timestamp=t0,
                source="fake-service",
                content="Deployed version v99.99.99 (Non-existent)",
            ),
        ],
        recommended_remediation=RecommendedRemediation(
            immediate_steps=["Fake step"],
            verification_metric="fake metric",
            rollback_plan="fake rollback",
        ),
    )

    result = GroundingVerifier.verify(report, incident)
    assert result.is_fully_grounded is False
    assert result.hallucination_rate == 1.0
    assert result.grounding_precision == 0.0
    assert result.verified_count == 0
    assert result.unverified_count == 3

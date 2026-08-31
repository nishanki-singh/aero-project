"""Deterministic grounding verification and hallucination detection engine."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional
from pydantic import BaseModel, Field

from src.schemas.diagnostic import AeroDiagnosticReport, SignalType, SupportingEvidence
from src.schemas.incident import Incident


class GroundedEvidenceItem(BaseModel):
    """Result of checking an individual evidence citation against raw telemetry."""
    evidence: SupportingEvidence
    is_grounded: bool
    verification_reason: str


class GroundingVerificationResult(BaseModel):
    """Aggregate grounding verification metrics for a diagnostic report."""
    incident_id: str
    total_citations: int
    verified_count: int
    unverified_count: int
    hallucination_rate: float = Field(..., description="Proportion of ungrounded citations (0.0 - 1.0).")
    grounding_precision: float = Field(..., description="Proportion of verified citations (0.0 - 1.0).")
    is_fully_grounded: bool
    evidence_details: List[GroundedEvidenceItem] = Field(default_factory=list)


class GroundingVerifier:
    """Verifies that every claim and citation in an AeroDiagnosticReport is strictly grounded in raw telemetry."""

    TIMESTAMP_TOLERANCE_SECONDS = 60

    @classmethod
    def verify(cls, report: AeroDiagnosticReport, incident: Incident) -> GroundingVerificationResult:
        """Verifies all evidence citations against the incident's raw telemetry."""
        telemetry = incident.telemetry
        details: List[GroundedEvidenceItem] = []

        for ev in report.supporting_evidence:
            item_result = cls._verify_single_evidence(ev, telemetry)
            details.append(item_result)

        total = len(details)
        verified = sum(1 for d in details if d.is_grounded)
        unverified = total - verified
        hallucination_rate = (unverified / total) if total > 0 else 0.0
        precision = (verified / total) if total > 0 else 1.0

        return GroundingVerificationResult(
            incident_id=report.incident_id,
            total_citations=total,
            verified_count=verified,
            unverified_count=unverified,
            hallucination_rate=round(hallucination_rate, 4),
            grounding_precision=round(precision, 4),
            is_fully_grounded=(unverified == 0),
            evidence_details=details,
        )

    @classmethod
    def _verify_single_evidence(
        cls,
        evidence: SupportingEvidence,
        telemetry,
    ) -> GroundedEvidenceItem:
        """Verifies a single evidence citation against corresponding telemetry signal type."""
        sig_type = evidence.signal_type
        content_lower = evidence.content.lower()
        source_lower = evidence.source.lower()

        # 1. Verify LOG signal
        if sig_type == SignalType.LOG:
            for log in telemetry.logs:
                # Match log message or attributes
                msg_match = any(
                    token in log.message.lower() for token in content_lower.split() if len(token) > 4
                ) or content_lower in log.message.lower()
                attr_match = any(
                    source_lower in str(v).lower() or content_lower in str(v).lower()
                    for v in log.attributes.values()
                )
                source_match = source_lower in log.service_name.lower() or (
                    log.attributes.get("pod") and source_lower in str(log.attributes.get("pod")).lower()
                )

                if (msg_match or attr_match) and (source_match or not source_lower):
                    # Check timestamp window
                    time_diff = abs((evidence.timestamp - log.timestamp).total_seconds())
                    if time_diff <= cls.TIMESTAMP_TOLERANCE_SECONDS:
                        return GroundedEvidenceItem(
                            evidence=evidence,
                            is_grounded=True,
                            verification_reason=f"Matched log entry on service '{log.service_name}' at {log.timestamp.isoformat()}",
                        )

            return GroundedEvidenceItem(
                evidence=evidence,
                is_grounded=False,
                verification_reason="No matching log entry found with cited content and timestamp in telemetry.",
            )

        # 2. Verify METRIC signal
        elif sig_type == SignalType.METRIC:
            for metric in telemetry.metrics:
                name_match = (
                    source_lower in metric.metric_name.lower()
                    or metric.metric_name.lower() in content_lower
                    or any(token in metric.metric_name.lower() for token in source_lower.split("/") if len(token) > 3)
                )
                label_match = any(
                    source_lower in str(v).lower() for v in metric.labels.values()
                )

                if name_match or label_match:
                    return GroundedEvidenceItem(
                        evidence=evidence,
                        is_grounded=True,
                        verification_reason=f"Matched metric series '{metric.metric_name}' on service '{metric.service_name}'",
                    )

            return GroundedEvidenceItem(
                evidence=evidence,
                is_grounded=False,
                verification_reason="Cited metric series was not found in telemetry metrics.",
            )

        # 3. Verify DEPLOYMENT signal
        elif sig_type == SignalType.DEPLOYMENT:
            for dep in telemetry.deployments:
                ver_match = dep.version.lower() in content_lower or dep.version.lower() in source_lower
                commit_match = dep.commit_hash.lower() in content_lower
                svc_match = dep.service_name.lower() in source_lower or dep.service_name.lower() in content_lower

                if ver_match or commit_match or svc_match:
                    return GroundedEvidenceItem(
                        evidence=evidence,
                        is_grounded=True,
                        verification_reason=f"Matched deployment event '{dep.version}' on service '{dep.service_name}'",
                    )

            return GroundedEvidenceItem(
                evidence=evidence,
                is_grounded=False,
                verification_reason="Cited deployment event was not found in telemetry deployments.",
            )

        # 4. Verify HEALTH signal
        elif sig_type == SignalType.HEALTH:
            for health in telemetry.health_signals:
                status_match = health.status.value.lower() in content_lower
                svc_match = health.service_name.lower() in source_lower or health.service_name.lower() in content_lower

                if status_match and svc_match:
                    return GroundedEvidenceItem(
                        evidence=evidence,
                        is_grounded=True,
                        verification_reason=f"Matched health record '{health.status.value}' on service '{health.service_name}'",
                    )

            return GroundedEvidenceItem(
                evidence=evidence,
                is_grounded=False,
                verification_reason="Cited health degradation was not found in telemetry health records.",
            )

        return GroundedEvidenceItem(
            evidence=evidence,
            is_grounded=False,
            verification_reason=f"Unknown signal type '{sig_type}'.",
        )

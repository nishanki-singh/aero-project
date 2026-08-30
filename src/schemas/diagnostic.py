"""Pydantic schemas for AI diagnostic reasoning outputs and evidence citations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Source telemetry type cited as diagnostic evidence."""
    LOG = "LOG"
    METRIC = "METRIC"
    DEPLOYMENT = "DEPLOYMENT"
    HEALTH = "HEALTH"


class ConfidenceRating(str, Enum):
    """Categorical confidence score rating."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SupportingEvidence(BaseModel):
    """Specific telemetry observation supporting the diagnostic conclusion."""
    signal_type: SignalType = Field(..., description="Type of evidence signal.")
    timestamp: datetime = Field(..., description="Timestamp when evidence occurred.")
    source: str = Field(..., description="Originating entity (e.g., pod name, metric name, deploy hash).")
    content: str = Field(..., description="Verbatim or summarized observation extracted from telemetry.")
    relevance: Optional[str] = Field(default=None, description="Explanation of why this supports the diagnosis.")


class ProbableRootCause(BaseModel):
    """Identified primary root cause."""
    title: str = Field(..., description="Short canonical title of the root cause.")
    description: str = Field(..., description="Detailed causal explanation distinguishing trigger from symptoms.")
    category: str = Field(..., description="Root cause taxonomy category (e.g., RESOURCE_EXHAUSTION_MEMORY).")
    trigger_event: Optional[str] = Field(default=None, description="Specific trigger initiating the failure sequence.")


class ConfidenceLevel(BaseModel):
    """Quantitative and qualitative confidence score."""
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0.")
    rating: ConfidenceRating = Field(..., description="Categorical rating (HIGH, MEDIUM, LOW).")
    rationale: str = Field(..., description="Reasoning justifying the confidence score.")


class HistoricalIncidentMatch(BaseModel):
    """Reference to a similar past postmortem retrieved via Engineering Memory (RAG)."""
    incident_id: str = Field(..., description="Past incident identifier.")
    title: str = Field(..., description="Title of past incident.")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity score.")
    resolution_summary: str = Field(..., description="How the past incident was mitigated.")


class RecommendedRemediation(BaseModel):
    """Human-in-the-loop remediation proposal."""
    immediate_steps: List[str] = Field(..., description="Step-by-step mitigation actions for on-call engineer.")
    dry_run_command: Optional[str] = Field(default=None, description="Safe verification or dry-run CLI command.")
    verification_metric: str = Field(..., description="Metric or signal confirming operational recovery.")
    rollback_plan: str = Field(..., description="Contingency rollback procedure if mitigation fails.")


class RunbookReference(BaseModel):
    """Reference to an operational runbook retrieved via RAG."""
    title: str = Field(..., description="Runbook title.")
    document_uri: str = Field(..., description="Cloud Storage or documentation URI.")
    pertinent_section: str = Field(..., description="Specific section or procedure name.")


class AeroDiagnosticReport(BaseModel):
    """Complete structured diagnostic output produced by AERO's AI Reasoning Engine."""
    incident_id: str = Field(..., description="Associated incident identifier.")
    service_name: str = Field(..., description="Primary affected microservice.")
    severity: str = Field(..., description="Incident severity level.")
    incident_summary: str = Field(..., description="Executive summary of incident onset and impact.")
    probable_root_cause: ProbableRootCause = Field(..., description="Identified root cause.")
    confidence_level: ConfidenceLevel = Field(..., description="Confidence assessment.")
    supporting_evidence: List[SupportingEvidence] = Field(default_factory=list, description="Citations to evidence.")
    similar_historical_incidents: List[HistoricalIncidentMatch] = Field(
        default_factory=list, description="Retrieved similar historical incidents from Engineering Memory."
    )
    recommended_remediation: RecommendedRemediation = Field(..., description="Actionable mitigation checklist.")
    relevant_runbook: Optional[RunbookReference] = Field(default=None, description="Relevant runbook section.")

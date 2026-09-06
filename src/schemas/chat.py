"""Pydantic schemas for Grounded SRE Copilot interactive reasoning and chat."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.schemas.diagnostic import SignalType


class EvidenceItem(BaseModel):
    """Specific observed telemetry fact supporting the Copilot answer."""
    signal_type: SignalType = Field(..., description="Type of evidence signal (LOG, METRIC, DEPLOYMENT, HEALTH).")
    source: str = Field(..., description="Originating service, container, or telemetry source.")
    description: str = Field(..., description="Verbatim or summarized observation extracted from telemetry.")
    timestamp: datetime | None = Field(default=None, description="Timestamp when evidence occurred.")
    metric_name: str | None = Field(default=None, description="Metric series name if signal_type is METRIC.")
    log_snippet: str | None = Field(default=None, description="Verbatim log snippet if signal_type is LOG.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Verification confidence score.")


class ChatRequest(BaseModel):
    """Request payload for SRE Copilot chat."""
    scenario_key: str = Field(..., description="Active benchmark scenario identifier.")
    message: str = Field(..., min_length=1, description="User question or prompt.")
    provider: str | None = Field(default="mock", description="AI provider ('mock' or 'vertex').")
    seed: int = Field(default=42, description="Random seed for benchmark telemetry.")


class ChatResponse(BaseModel):
    """Structured, evidence-grounded Copilot response payload."""
    scenario_key: str = Field(..., description="Active scenario key for the conversation context.")
    answer: str = Field(..., description="High-level markdown summary answering the user query.")
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Observed facts directly present in scenario telemetry (logs, metrics, deployments, health).",
    )
    inferences: list[str] = Field(
        default_factory=list,
        description="Derived causal interpretations and deductions based on the observed evidence.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable SRE recommendations and next verification steps (informational only).",
    )
    confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Overall confidence score.")
    grounded: bool = Field(
        default=True,
        description="True if all cited evidence items strictly exist in active telemetry.",
    )
    failed_claims: list[str] = Field(
        default_factory=list,
        description="Unverified claims or missing evidence identified during grounding validation.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when response was generated.",
    )

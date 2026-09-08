"""Pydantic schemas for AERO Phase 4 Stage 4G: Pre-Deployment Risk Advisor."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskSeverity(str, Enum):
    """Overall and finding-level risk severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskCategory(str, Enum):
    """Taxonomy of deployment and configuration risk categories."""

    RESOURCE_LIMITS = "RESOURCE_LIMITS"
    DATABASE_POOL = "DATABASE_POOL"
    TIMEOUTS_DEPENDENCIES = "TIMEOUTS_DEPENDENCIES"
    HEALTH_READINESS = "HEALTH_READINESS"
    ROLLBACK_STRATEGY = "ROLLBACK_STRATEGY"
    DANGEROUS_CONFIG = "DANGEROUS_CONFIG"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    CRITICAL_SERVICE = "CRITICAL_SERVICE"
    INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"


class ProposedChange(BaseModel):
    """Structured representation of a proposed deployment or configuration change."""

    model_config = ConfigDict(extra="allow")

    service: str = Field(..., description="Target service name (e.g. order-service, worker-service)")
    change_type: str = Field(
        default="deployment",
        description="Type of change: deployment, config, resource, or dependency",
    )
    description: str = Field(..., description="Human-readable description of the intended change")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value parameters (e.g. memory_limit_mb, pool_size, timeout_ms, readiness_probe_enabled)",
    )
    environment: str = Field(default="production", description="Target environment (production, staging, etc.)")
    rollback_plan: str | None = Field(default=None, description="Rollback version or procedure")
    tags: list[str] = Field(default_factory=list, description="Metadata tags for change classification")


class RiskFinding(BaseModel):
    """A single deterministic risk finding with 3-tier evidence and reasoning separation."""

    model_config = ConfigDict(extra="ignore")

    rule_id: str = Field(..., description="Unique rule identifier (e.g. RISK-RES-001)")
    title: str = Field(..., description="Concise title of the detected risk")
    severity: RiskSeverity = Field(..., description="Severity of this finding")
    category: RiskCategory = Field(..., description="Taxonomy category")
    observed_facts: list[str] = Field(
        default_factory=list,
        description="Factual observations extracted from the proposed change or telemetry baseline",
    )
    derived_risk: str = Field(
        ...,
        description="Causal risk assessment explaining why the change is risky",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable preventive recommendations before deployment",
    )
    score_impact: int = Field(
        default=10,
        description="Point contribution to the overall risk score (0-100 scale)",
    )


class RiskAnalysisRequest(BaseModel):
    """Request payload for pre-deployment risk analysis."""

    model_config = ConfigDict(extra="ignore")

    proposed_change: ProposedChange = Field(..., description="The proposed change specification")
    scenario_key: str | None = Field(
        default=None,
        description="Optional active scenario key for incident telemetry cross-referencing",
    )
    provider: str = Field(
        default="deterministic",
        description="Risk analysis provider ('deterministic' or 'mock')",
    )


class RiskAnalysisResponse(BaseModel):
    """Response payload containing comprehensive pre-deployment risk evaluation."""

    model_config = ConfigDict(extra="ignore")

    overall_severity: RiskSeverity = Field(..., description="Aggregated risk severity level")
    risk_score: int = Field(..., ge=0, le=100, description="Normalized risk score from 0 (safest) to 100 (highest risk)")
    is_safe_to_deploy: bool = Field(..., description="Whether the change is safe to proceed without blocking gates")
    findings: list[RiskFinding] = Field(default_factory=list, description="List of detected risk findings")
    observed_facts_summary: list[str] = Field(
        default_factory=list,
        description="Summary list of all factual observations",
    )
    preventive_recommendations: list[str] = Field(
        default_factory=list,
        description="Aggregated list of actionable preventive recommendations",
    )
    rule_evaluation_count: int = Field(default=0, description="Total number of deterministic rules evaluated")
    scenario_context_applied: bool = Field(
        default=False,
        description="Whether active incident telemetry was cross-referenced in the analysis",
    )
    insufficient_data: bool = Field(
        default=False,
        description="True if input was too sparse to perform a full evaluation",
    )
    explanation: str = Field(
        default="",
        description="High-level narrative summary of the overall pre-deployment assessment",
    )

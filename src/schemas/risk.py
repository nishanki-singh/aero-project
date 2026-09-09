"""Pydantic schemas for AERO Phase 4 Stage 4G: Pre-Deployment Risk Advisor."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    PREVENTION_ALIGNMENT = "PREVENTION_ALIGNMENT"
    RECURRENCE_RISK = "RECURRENCE_RISK"
    UNADDRESSED_FAILURE_MODE = "UNADDRESSED_FAILURE_MODE"


class DiagnosisContext(BaseModel):
    """Structured diagnosis context extracted from incident evidence for risk evaluation."""

    model_config = ConfigDict(extra="ignore")

    root_cause: str | None = Field(
        default=None,
        description="Diagnosed primary root cause summary (e.g. Heap memory exhaustion / OOMKilled)",
    )
    diagnosis_category: str | None = Field(
        default=None,
        description="Diagnosed taxonomy category (e.g. RESOURCE_EXHAUSTION_MEMORY, DATABASE_POOL_EXHAUSTION)",
    )
    diagnosis_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of the incident diagnosis (0.0 to 1.0)",
    )
    observed_evidence: list[str] = Field(
        default_factory=list,
        description="Key observed telemetry evidence facts from the active incident",
    )
    telemetry_facts: list[str] = Field(
        default_factory=list,
        description="Quantitative telemetry facts (e.g. peak memory 99.8%, active connections 100/100)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="AERO recommended mitigation actions for this incident failure mode",
    )
    mitigation_actions: list[str] = Field(
        default_factory=list,
        description="Actionable preventive mitigation steps",
    )


class DiagnosisAlignmentInfo(BaseModel):
    """Evaluation of how well the proposed change addresses the diagnosed root cause."""

    model_config = ConfigDict(extra="ignore")

    root_cause: str = Field(default="", description="Diagnosed root cause")
    diagnosis_category: str = Field(default="", description="Diagnosed failure category")
    observed_peak: str = Field(default="", description="Observed telemetry peak or saturation level")
    aero_recommendations: list[str] = Field(
        default_factory=list,
        description="AERO recommendations for mitigating this failure mode",
    )
    is_aligned: bool = Field(
        default=True,
        description="Whether proposed change aligns with and addresses the diagnosed root cause",
    )
    alignment_summary: str = Field(
        default="",
        description="Concise summary of diagnosis alignment and mitigation efficacy",
    )


class RecurrencePrediction(BaseModel):
    """Deterministic recurrence risk prediction for the proposed deployment."""

    model_config = ConfigDict(extra="ignore")

    risk: RiskSeverity = Field(
        default=RiskSeverity.LOW,
        description="Predicted recurrence risk level (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    likely_recurrence: bool = Field(
        default=False,
        description="Whether the diagnosed incident failure mode is likely to recur under this change",
    )
    reason: str = Field(
        default="",
        description="Deterministic causal reasoning explaining why recurrence is or is not expected",
    )


class EvaluatedChangeSummary(BaseModel):
    """Structured summary of the explicit proposed change evaluated by Risk Advisor."""

    model_config = ConfigDict(extra="allow")

    service: str = Field(default="", description="Target service name")
    change_type: str = Field(default="deployment", description="Type of change")
    description: str = Field(default="", description="Description of the change")
    environment: str = Field(default="production", description="Target environment")
    memory_limit_mb: float | int | None = Field(default=None, description="Configured container memory limit")
    memory_request_mb: float | int | None = Field(default=None, description="Configured container memory request")
    cpu_limit: float | int | str | None = Field(default=None, description="Configured CPU limit")
    concurrency: int | None = Field(default=None, description="Configured worker / thread concurrency")
    pool_max: int | None = Field(default=None, description="Configured connection pool max size")
    timeout_seconds: float | int | None = Field(default=None, description="Configured timeout")
    image_tag: str | None = Field(default=None, description="Container image tag")
    rollback_plan: str | None = Field(default=None, description="Documented rollback plan or version target")
    rollback_version: str | None = Field(default=None, description="Target rollback version")
    debug_mode: bool = Field(default=False, description="Whether debug mode / verbose logging is active")
    log_level: str | None = Field(default=None, description="Configured logging level")
    readiness_probe_enabled: bool = Field(default=True, description="Whether readiness probe is enabled")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Raw key-value parameters")


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

    # Optional direct parameter convenience accessors
    memory_limit_mb: float | int | None = Field(default=None, description="Container memory limit in MB")
    memory_request_mb: float | int | None = Field(default=None, description="Container memory request in MB")
    cpu_limit: float | int | str | None = Field(default=None, description="Container CPU limit")
    cpu_request: float | int | str | None = Field(default=None, description="Container CPU request")
    concurrency: int | None = Field(default=None, description="Worker or thread concurrency")
    pool_max: int | None = Field(default=None, description="Database connection pool size")
    timeout_seconds: float | int | None = Field(default=None, description="RPC timeout in seconds")
    image_tag: str | None = Field(default=None, description="Container image tag")
    rollback_version: str | None = Field(default=None, description="Target rollback version")
    debug_mode: bool | None = Field(default=None, description="Debug mode flag")
    log_level: str | None = Field(default=None, description="Logging level")
    readiness_probe_enabled: bool | None = Field(default=None, description="Readiness probe toggle")
    liveness_initial_delay_seconds: int | None = Field(default=None, description="Liveness initial delay")

    @model_validator(mode="before")
    @classmethod
    def _sync_parameters(cls, data: Any) -> Any:
        """Ensure direct fields are populated from parameters dict if not explicitly provided."""
        if isinstance(data, dict):
            params = data.get("parameters") or {}
            field_mappings = {
                "memory_limit_mb": ["memory_limit_mb", "memory_limit"],
                "memory_request_mb": ["memory_request_mb", "memory_request"],
                "cpu_limit": ["cpu_limit_cores", "cpu_limit"],
                "cpu_request": ["cpu_request_cores", "cpu_request"],
                "concurrency": ["concurrency", "worker_count", "workers"],
                "pool_max": ["pool_max", "pool_max_size", "db_pool_size"],
                "timeout_seconds": ["timeout_seconds", "timeout_ms"],
                "image_tag": ["image_tag"],
                "rollback_version": ["rollback_version"],
                "debug_mode": ["debug_mode"],
                "log_level": ["log_level"],
                "readiness_probe_enabled": ["readiness_probe_enabled"],
                "liveness_initial_delay_seconds": ["liveness_initial_delay_seconds"],
            }
            for direct_key, param_keys in field_mappings.items():
                if data.get(direct_key) is None:
                    for pk in param_keys:
                        if pk in params and params[pk] is not None:
                            data[direct_key] = params[pk]
                            break
        return data


class RiskFinding(BaseModel):
    """A single deterministic risk finding with 3-tier evidence and reasoning separation."""

    model_config = ConfigDict(extra="ignore")

    rule_id: str = Field(..., description="Unique rule identifier (e.g. RISK-RES-001, RISK-PREV-001)")
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
        description="Optional active scenario key for incident telemetry and diagnosis cross-referencing",
    )
    diagnosis_context: DiagnosisContext | None = Field(
        default=None,
        description="Optional explicit incident diagnosis context (root cause, evidence, recommendations)",
    )
    provider: str = Field(
        default="deterministic",
        description="Risk analysis provider ('deterministic' or 'mock')",
    )


class RiskAnalysisResponse(BaseModel):
    """Response payload containing comprehensive pre-deployment risk evaluation."""

    model_config = ConfigDict(extra="ignore")

    overall_severity: RiskSeverity = Field(..., description="Aggregated deployment risk severity level")
    risk_score: int = Field(..., ge=0, le=100, description="Normalized deployment risk score from 0 (safest) to 100 (highest risk)")
    is_safe_to_deploy: bool = Field(..., description="Whether the change is safe to proceed without blocking gates")
    decision: str = Field(
        default="SAFE",
        description="Deployment decision gate: SAFE, WARNING, HIGH_RISK, or BLOCKED",
    )
    findings: list[RiskFinding] = Field(default_factory=list, description="Combined list of all detected risk findings")
    generic_findings: list[RiskFinding] = Field(
        default_factory=list,
        description="Findings from generic SRE deployment safety checks (RISK-RES, RISK-POOL, RISK-TIMEOUT, etc.)",
    )
    prevention_findings: list[RiskFinding] = Field(
        default_factory=list,
        description="Findings from diagnosis-aware recurrence prevention checks (RISK-PREV-*)",
    )
    diagnosis_alignment: DiagnosisAlignmentInfo = Field(
        default_factory=DiagnosisAlignmentInfo,
        description="Evaluation of proposed change alignment with incident root cause diagnosis",
    )
    predicted_recurrence: RecurrencePrediction = Field(
        default_factory=RecurrencePrediction,
        description="Deterministic recurrence risk prediction under proposed change",
    )
    evaluated_change: EvaluatedChangeSummary = Field(
        default_factory=EvaluatedChangeSummary,
        description="Structured summary of the evaluated proposed change configuration",
    )
    evidence_used: list[str] = Field(
        default_factory=list,
        description="List of observed telemetry facts and diagnostic evidence cross-referenced in evaluation",
    )
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
        description="Whether active incident telemetry and diagnosis were cross-referenced in the analysis",
    )
    insufficient_data: bool = Field(
        default=False,
        description="True if input was too sparse to perform a full evaluation",
    )
    explanation: str = Field(
        default="",
        description="High-level narrative summary of the overall pre-deployment assessment",
    )

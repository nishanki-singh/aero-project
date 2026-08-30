"""Pydantic schemas for ground-truth benchmark scenarios and evaluation criteria."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas.diagnostic import SignalType
from src.schemas.incident import Incident


class ExpectedEvidence(BaseModel):
    """Ground-truth definition of a specific telemetry signal that must be cited."""
    signal_type: SignalType = Field(..., description="Expected signal type (LOG, METRIC, DEPLOYMENT, HEALTH).")
    pattern: str = Field(..., description="Substring or regex pattern expected in the cited evidence content/source.")
    description: str = Field(..., description="Explanation of why this signal is critical evidence.")
    is_mandatory: bool = Field(default=True, description="Whether omission penalizes the grounding score.")


class ExpectedRemediation(BaseModel):
    """Ground-truth expected remediation actions and recovery verification."""
    key_actions: List[str] = Field(..., description="Key phrases or actions required in the mitigation plan.")
    expected_verification_metric: str = Field(..., description="Expected metric for verifying recovery.")


class GroundTruthScenario(BaseModel):
    """Canonical ground-truth specification for a benchmark incident scenario."""
    scenario_id: str = Field(..., description="Unique scenario ID (e.g., BENCHMARK-OOM-001).")
    scenario_name: str = Field(..., description="Human-readable scenario title.")
    category: str = Field(..., description="Taxonomy failure category (e.g., RESOURCE_EXHAUSTION_MEMORY).")
    affected_service: str = Field(..., description="Primary affected microservice.")
    trigger_event: str = Field(..., description="Specific event triggering the incident onset.")
    root_cause_summary: str = Field(..., description="True root cause summary for scoring.")
    expected_root_cause_category: str = Field(..., description="Canonical category for automated exact-match scoring.")
    expected_evidence_signals: List[ExpectedEvidence] = Field(
        default_factory=list, description="List of evidence signals the model is required to cite."
    )
    expected_remediation: ExpectedRemediation = Field(..., description="Expected mitigation plan attributes.")
    expected_diagnostic_conclusion: str = Field(..., description="Expected high-level diagnostic verdict.")
    evaluation_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata and scoring weights for benchmarking."
    )


class BenchmarkScenarioBundle(BaseModel):
    """Coupled benchmark container holding both the ground-truth definition and the generated incident telemetry."""
    ground_truth: GroundTruthScenario = Field(..., description="The objective ground-truth benchmark rules.")
    incident: Incident = Field(..., description="The generated multi-signal incident telemetry.")

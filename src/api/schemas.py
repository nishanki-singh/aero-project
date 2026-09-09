"""Pydantic request and response schemas for the AERO FastAPI Gateway."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.engine.grounding_verifier import GroundingVerificationResult
from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.incident import Incident
from src.schemas.postmortem import AeroPostmortem


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="HEALTHY", description="Service health status.")
    version: str = Field(default="1.0.0", description="AERO API version.")
    environment: str = Field(..., description="Runtime environment.")
    gcp_project_id: str = Field(..., description="Active Google Cloud project ID.")
    gcp_region: str = Field(..., description="Active Google Cloud region.")


class ConfigResponse(BaseModel):
    """System configuration inspection schema."""
    project_id: str
    region: str
    environment: str
    reasoning_model: str
    fast_model: str
    embedding_model: str
    diagnostic_provider: str


class ScenarioSummaryResponse(BaseModel):
    """Concise metadata summary of a benchmark scenario."""
    scenario_id: str = Field(..., description="Unique scenario ID (e.g. BENCHMARK-OOM-001).")
    scenario_name: str = Field(..., description="Human-readable scenario title.")
    category: str = Field(..., description="Taxonomy classification category.")
    affected_service: str = Field(..., description="Microservice affected.")
    trigger_event: str = Field(..., description="Trigger summary.")


class DiagnoseRequest(BaseModel):
    """Payload to trigger AI diagnostic reasoning."""
    incident: Incident = Field(..., description="Full incident telemetry payload.")
    provider: str | None = Field(default=None, description="Diagnostic provider override: 'mock', 'vertex', 'auto'.")


class DiagnoseResponse(BaseModel):
    """Diagnostic output including evidence grounding result."""
    report: AeroDiagnosticReport = Field(..., description="Structured diagnostic report.")
    grounding: GroundingVerificationResult = Field(..., description="Deterministic grounding verification result.")
    duration_sec: float = Field(..., description="Inference and verification duration in seconds.")
    provider: str = Field(default="mock", description="Engine provider that generated the report ('mock' or 'live').")


class TimelineRequest(BaseModel):
    """Request payload for timeline synthesis."""
    incident: Incident = Field(..., description="Incident with telemetry.")
    diagnostic_report: AeroDiagnosticReport | None = Field(default=None, description="Optional diagnostic report to enrich timeline.")


class ReplayRequest(BaseModel):
    """Request payload for incident state replay."""
    incident: Incident = Field(..., description="Incident with telemetry.")
    interval_seconds: int = Field(default=60, ge=10, le=300, description="Step sampling interval in seconds.")


class PostmortemRequest(BaseModel):
    """Request payload for postmortem authoring."""
    incident: Incident = Field(..., description="Incident context and telemetry.")
    diagnostic_report: AeroDiagnosticReport | None = Field(default=None, description="Optional pre-computed diagnostic report.")
    provider: str | None = Field(default=None, description="Provider override: 'mock', 'vertex', 'auto'.")


class PostmortemResponse(BaseModel):
    """Postmortem output including structured JSON and publication-ready Markdown."""
    postmortem: AeroPostmortem = Field(..., description="Structured Google SRE postmortem object.")
    markdown: str = Field(..., description="Formatted publication-ready Markdown document.")
    provider: str = Field(default="mock", description="Engine provider that authored the postmortem ('mock' or 'live').")


class EvaluationRequest(BaseModel):
    """Request payload to execute benchmark suite evaluation."""
    scenario_keys: list[str] | None = Field(default=None, description="Specific scenario keys to evaluate (e.g. ['oom_kill']). If omitted, all scenarios run.")
    provider: str | None = Field(default="mock", description="Diagnostic provider to benchmark: 'mock', 'vertex'.")
    seed: int = Field(default=42, description="Random seed for deterministic benchmark generation.")

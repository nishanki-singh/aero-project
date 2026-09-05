"""Pydantic schemas for Google SRE standard automated postmortems and action items."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.schemas.diagnostic import RecommendedRemediation
from src.schemas.timeline import TimelineMilestone


class ActionItemPriority(str, Enum):
    """Priority level for postmortem corrective engineering tasks."""
    P0 = "P0"  # Blocker / Critical immediate prevention
    P1 = "P1"  # High priority / Next sprint
    P2 = "P2"  # Medium priority / Backlog
    P3 = "P3"  # Low priority / Technical hygiene


class ActionItemCategory(str, Enum):
    """Categorical domain for preventative action items."""
    MITIGATION = "MITIGATION"
    MONITORING = "MONITORING"
    RESILIENCE = "RESILIENCE"
    PROCESS = "PROCESS"
    TESTING = "TESTING"


class ActionItem(BaseModel):
    """Concrete, assigned preventative engineering task arising from postmortem analysis."""
    id: str = Field(..., description="Action item unique ID (e.g. ACT-001).")
    title: str = Field(..., description="Short action summary.")
    description: str = Field(..., description="Detailed technical requirements for prevention.")
    category: ActionItemCategory = Field(..., description="Category of action.")
    priority: ActionItemPriority = Field(..., description="Action item priority.")
    owner: str = Field(..., description="Assigned engineering team or role.")
    estimated_effort: str = Field(..., description="Estimated effort (e.g., '1 day', '1 sprint').")
    verification: str = Field(..., description="Criterion or test proving action was successful.")


class FiveWhysAnalysis(BaseModel):
    """Structured causal step in the Five-Whys root cause analysis chain."""
    level: int = Field(..., ge=1, le=5, description="1 to 5 depth level.")
    why: str = Field(..., description="Observed symptom or intermediary state.")
    because: str = Field(..., description="Underlying cause or enabling condition.")


class RootCauseSummary(BaseModel):
    """Comprehensive causal synthesis for postmortem documentation."""
    title: str = Field(..., description="Root cause canonical title.")
    category: str = Field(..., description="Taxonomy classification category.")
    trigger_event: str = Field(..., description="Exact trigger that initiated the failure sequence.")
    causal_chain: str = Field(..., description="End-to-end narrative from trigger to cascading failure.")


class ImpactSummary(BaseModel):
    """Quantitative and qualitative assessment of outage blast radius."""
    affected_service: str = Field(..., description="Primary affected microservice.")
    severity: str = Field(..., description="Incident severity level.")
    total_downtime_minutes: float = Field(..., description="Total duration of user-facing degradation in minutes.")
    failed_requests_estimate: str | None = Field(default=None, description="Estimated number or percentage of dropped/failed requests.")
    impacted_customers_or_flows: str = Field(..., description="User journeys or customer cohorts affected.")


class AeroPostmortem(BaseModel):
    """Complete, publication-ready postmortem document conforming to Google SRE standards."""
    postmortem_id: str = Field(..., description="Unique postmortem identifier.")
    incident_id: str = Field(..., description="Associated incident ID.")
    title: str = Field(..., description="Official postmortem title.")
    service_name: str = Field(..., description="Primary microservice.")
    severity: str = Field(..., description="Incident severity.")
    status: str = Field(default="PUBLISHED", description="Document status: DRAFT, REVIEWED, PUBLISHED.")
    created_at: datetime = Field(..., description="Creation timestamp.")
    executive_summary: str = Field(..., description="High-level narrative for engineering leadership.")
    impact: ImpactSummary = Field(..., description="Outage blast radius and impact breakdown.")
    root_cause: RootCauseSummary = Field(..., description="Causal analysis with trigger and taxonomy.")
    five_whys: list[FiveWhysAnalysis] = Field(default_factory=list, description="5-Whys causal progression.")
    timeline_milestones: list[TimelineMilestone] = Field(default_factory=list, description="Chronological event log.")
    remediation_performed: RecommendedRemediation = Field(..., description="Actions executed to stabilize the service.")
    action_items: list[ActionItem] = Field(default_factory=list, description="Assigned preventative engineering tasks.")
    lessons_learned_what_went_well: list[str] = Field(default_factory=list, description="Operational successes during triage.")
    lessons_learned_what_went_wrong: list[str] = Field(default_factory=list, description="Gaps, delays, or tooling deficiencies.")
    lessons_learned_where_we_got_lucky: list[str] = Field(default_factory=list, description="Fortuitous factors mitigating worse impact.")

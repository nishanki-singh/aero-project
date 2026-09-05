"""Pydantic schemas for chronological incident timelines and state replay snapshots."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MilestoneType(str, Enum):
    """Semantic milestone marker type in incident progression."""
    ANOMALY_ONSET = "ANOMALY_ONSET"
    ALERT_FIRED = "ALERT_FIRED"
    TRIAGE_START = "TRIAGE_START"
    PEAK_IMPACT = "PEAK_IMPACT"
    MITIGATION_APPLIED = "MITIGATION_APPLIED"
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RESOLVED = "RESOLVED"


class TimelineMilestone(BaseModel):
    """Chronological event marker along the incident lifecycle."""
    timestamp: datetime = Field(..., description="Timestamp of milestone event.")
    milestone_type: MilestoneType = Field(..., description="Semantic type of the milestone.")
    title: str = Field(..., description="Concise title of the event.")
    description: str = Field(..., description="Detailed description with context and observations.")
    source_service: str = Field(..., description="Microservice or subsystem associated with the event.")
    source_signal: str = Field(..., description="Source telemetry signal: LOG, METRIC, DEPLOYMENT, HEALTH, OPERATOR.")
    evidence_ref: str | None = Field(default=None, description="Reference link or excerpt of source evidence.")


class IncidentTimeline(BaseModel):
    """Complete synthesized incident timeline with lifecycle durations."""
    incident_id: str = Field(..., description="Associated incident ID.")
    service_name: str = Field(..., description="Primary affected microservice.")
    time_window_start: datetime = Field(..., description="Observation start time.")
    time_window_end: datetime = Field(..., description="Observation end time.")
    total_duration_minutes: float = Field(..., description="Total incident observation duration in minutes.")
    time_to_detect_minutes: float | None = Field(default=None, description="Minutes from onset to triage start.")
    time_to_mitigate_minutes: float | None = Field(default=None, description="Minutes from onset to mitigation applied.")
    milestones: list[TimelineMilestone] = Field(default_factory=list, description="Ordered milestone list.")


class SystemReplaySnapshot(BaseModel):
    """Discretized system operational state snapshot at a specific point in time."""
    timestamp: datetime = Field(..., description="Timestamp of the snapshot.")
    step_index: int = Field(..., description="Zero-based step index in the replay sequence.")
    service_name: str = Field(..., description="Affected service name.")
    health_status: str = Field(..., description="HEALTHY, DEGRADED, CRITICAL, or RECOVERING.")
    error_rate_pct: float = Field(..., ge=0.0, le=100.0, description="Active error rate percentage.")
    latency_p99_ms: float = Field(..., ge=0.0, description="P99 latency in milliseconds.")
    primary_metric_name: str | None = Field(default=None, description="Primary bottleneck metric name.")
    primary_metric_value: float | None = Field(default=None, description="Primary bottleneck metric value.")
    primary_metric_unit: str | None = Field(default=None, description="Unit of primary metric.")
    active_error_count: int = Field(default=0, description="Count of error logs in this time interval.")
    sample_error_log: str | None = Field(default=None, description="Representative error log message.")
    active_annotation: str | None = Field(default=None, description="Key event occurring at this step.")


class IncidentReplaySeries(BaseModel):
    """Complete timeseries array of system snapshots enabling step-through replay scrubbing."""
    incident_id: str = Field(..., description="Associated incident ID.")
    service_name: str = Field(..., description="Primary affected microservice.")
    interval_seconds: int = Field(default=60, description="Sampling bucket interval in seconds.")
    total_steps: int = Field(..., description="Total number of replay steps.")
    snapshots: list[SystemReplaySnapshot] = Field(default_factory=list, description="Ordered replay snapshots.")

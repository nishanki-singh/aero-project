"""Pydantic schemas for incident definitions and correlated telemetry payloads."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.schemas.telemetry import (
    DeploymentEvent,
    LogEntry,
    MetricSeries,
    ServiceHealth,
)


class IncidentSeverity(str, Enum):
    """Incident severity classification."""
    SEV1_CRITICAL = "SEV1_CRITICAL"
    SEV2_HIGH = "SEV2_HIGH"
    SEV3_MEDIUM = "SEV3_MEDIUM"
    SEV4_LOW = "SEV4_LOW"


class IncidentStatus(str, Enum):
    """Lifecycle state of an incident."""
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"


class IncidentMetadata(BaseModel):
    """Core administrative and impact metadata for an incident."""
    incident_id: str = Field(..., description="Unique incident identifier (e.g., INC-20260830-001).")
    title: str = Field(..., description="Short descriptive title of the incident.")
    severity: IncidentSeverity = Field(..., description="Severity classification.")
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, description="Current resolution status.")
    affected_service: str = Field(..., description="Primary service affected.")
    impact_summary: str = Field(..., description="Summary of customer or system impact.")
    detected_at: datetime = Field(..., description="Timestamp when anomaly or alert triggered.")
    resolved_at: datetime | None = Field(default=None, description="Timestamp when incident was resolved.")


class TelemetryPayload(BaseModel):
    """Correlated multi-signal telemetry bundle for the incident time window."""
    time_window_start: datetime = Field(..., description="Start of observation window (ISO 8601).")
    time_window_end: datetime = Field(..., description="End of observation window (ISO 8601).")
    logs: list[LogEntry] = Field(default_factory=list, description="Correlated application and system logs.")
    metrics: list[MetricSeries] = Field(default_factory=list, description="Time series golden signals and resource metrics.")
    deployments: list[DeploymentEvent] = Field(default_factory=list, description="Recent deployment and config changes.")
    health_signals: list[ServiceHealth] = Field(default_factory=list, description="Service health check observations.")


class Incident(BaseModel):
    """Full incident entity combining metadata with correlated multi-source telemetry."""
    metadata: IncidentMetadata = Field(..., description="Incident administrative metadata.")
    telemetry: TelemetryPayload = Field(..., description="Correlated telemetry window.")

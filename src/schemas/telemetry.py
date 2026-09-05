"""Pydantic schemas for multi-signal cloud telemetry."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """Standard logging severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class HealthStatus(str, Enum):
    """Service health state."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class LogEntry(BaseModel):
    """Structured log record representing application, system, or container logs."""
    timestamp: datetime = Field(..., description="Timestamp of the log entry (ISO 8601).")
    service_name: str = Field(..., description="Name of the originating microservice.")
    log_level: LogLevel = Field(..., description="Severity level.")
    message: str = Field(..., description="Log message or stack trace.")
    trace_id: str | None = Field(default=None, description="Distributed tracing identifier.")
    span_id: str | None = Field(default=None, description="Span identifier.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Structured key-value context.")


class MetricPoint(BaseModel):
    """Single sample point in a metric time series."""
    timestamp: datetime = Field(..., description="Timestamp of the metric observation.")
    value: float = Field(..., description="Observed numeric value.")


class MetricSeries(BaseModel):
    """Time-series metric representing resource utilization, throughput, latency, or errors."""
    metric_name: str = Field(..., description="Unique metric identifier (e.g., container/memory_utilization).")
    service_name: str = Field(..., description="Microservice associated with this metric.")
    unit: str = Field(..., description="Measurement unit (e.g., percent, count, ms, bytes).")
    points: list[MetricPoint] = Field(default_factory=list, description="Ordered time series sample points.")
    labels: dict[str, str] = Field(default_factory=dict, description="Metric metadata labels.")


class DeploymentEvent(BaseModel):
    """Record of a code deployment, container rollout, or configuration change."""
    timestamp: datetime = Field(..., description="Timestamp when deployment took effect.")
    service_name: str = Field(..., description="Target service modified.")
    version: str = Field(..., description="Release tag or version identifier (e.g., v2.4.1).")
    commit_hash: str = Field(..., description="Git commit hash.")
    deployed_by: str = Field(default="ci-cd-bot", description="Author or pipeline triggering deployment.")
    change_summary: str = Field(..., description="Human-readable description of change or diff.")
    environment: str = Field(default="production", description="Target environment.")


class ServiceHealth(BaseModel):
    """Periodic health-check observation representing service uptime and golden signals."""
    timestamp: datetime = Field(..., description="Health check timestamp.")
    service_name: str = Field(..., description="Target service.")
    status: HealthStatus = Field(..., description="Operational status.")
    latency_p99_ms: float = Field(..., description="P99 response latency in milliseconds.")
    error_rate_pct: float = Field(..., description="HTTP 5xx or error response percentage (0-100).")
    details: str | None = Field(default=None, description="Additional status message.")

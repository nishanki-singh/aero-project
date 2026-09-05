"""Multi-signal telemetry aggregator and pre-filter pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.incident import Incident
from src.schemas.telemetry import (
    DeploymentEvent,
    HealthStatus,
    LogEntry,
    LogLevel,
    ServiceHealth,
)


class ErrorLogCluster(BaseModel):
    """Cluster of similar error logs with occurrence count and sample record."""
    service_name: str
    log_level: LogLevel
    pattern_summary: str
    count: int
    first_seen: datetime
    last_seen: datetime
    sample_log: LogEntry


class MetricAnomaly(BaseModel):
    """Extracted anomalous metric series with min/max values and observed delta."""
    metric_name: str
    service_name: str
    unit: str
    baseline_value: float
    peak_value: float
    delta_pct: float
    description: str
    labels: dict[str, str] = Field(default_factory=dict)


class CorrelatedTelemetrySummary(BaseModel):
    """Normalized, noise-filtered telemetry context ready for AI prompt composition."""
    incident_id: str
    affected_service: str
    time_window_start: datetime
    time_window_end: datetime
    total_raw_logs: int
    error_clusters: list[ErrorLogCluster]
    metric_anomalies: list[MetricAnomaly]
    recent_deployments: list[DeploymentEvent]
    health_degradations: list[ServiceHealth]
    unaffected_services: list[str]


class TelemetryCorrelator:
    """Aggregates, normalizes, and filters multi-signal telemetry to isolate anomalous patterns."""

    @staticmethod
    def correlate(incident: Incident) -> CorrelatedTelemetrySummary:
        """Processes an incident's telemetry payload into a structured, noise-reduced summary."""
        telemetry = incident.telemetry
        metadata = incident.metadata

        # 1. Process and Cluster Error Logs (WARN, ERROR, FATAL)
        error_logs = [
            log for log in telemetry.logs
            if log.log_level in (LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL)
        ]

        clusters: dict[str, list[LogEntry]] = {}
        for log in error_logs:
            # Cluster key: service + first 40 chars of message (or error class attribute)
            err_class = log.attributes.get("error_class") or log.attributes.get("reason")
            key = f"{log.service_name}:{log.log_level.value}:{err_class or log.message[:45]}"
            clusters.setdefault(key, []).append(log)

        error_clusters: list[ErrorLogCluster] = []
        for key, logs in clusters.items():
            first_log = min(logs, key=lambda x: x.timestamp)
            last_log = max(logs, key=lambda x: x.timestamp)
            error_clusters.append(
                ErrorLogCluster(
                    service_name=first_log.service_name,
                    log_level=first_log.log_level,
                    pattern_summary=first_log.message[:120],
                    count=len(logs),
                    first_seen=first_log.timestamp,
                    last_seen=last_log.timestamp,
                    sample_log=first_log,
                )
            )
        error_clusters.sort(key=lambda x: x.count, reverse=True)

        # 2. Extract Metric Anomalies
        metric_anomalies: list[MetricAnomaly] = []
        for series in telemetry.metrics:
            if not series.points:
                continue
            values = [p.value for p in series.points]
            max_val = max(values)
            baseline = values[0] if values else 0.0

            # Identify if metric shows significant fluctuation, spike, or saturation
            is_anomaly = False
            delta_pct = 0.0
            desc = ""

            if baseline > 0:
                delta_pct = ((max_val - baseline) / baseline) * 100.0
            elif max_val > 0:
                delta_pct = 100.0

            if max_val >= 90.0 and series.unit == "percent":
                is_anomaly = True
                desc = f"Saturated at {max_val}{series.unit}"
            elif delta_pct > 100.0 or delta_pct < -50.0:
                is_anomaly = True
                desc = f"Shifted from {baseline} to {max_val} {series.unit} (delta: {delta_pct:+.1f}%)"
            elif max_val > 1000.0 and series.unit == "ms":
                is_anomaly = True
                desc = f"Latency spike to {max_val}ms (baseline: {baseline}ms)"

            if is_anomaly:
                metric_anomalies.append(
                    MetricAnomaly(
                        metric_name=series.metric_name,
                        service_name=series.service_name,
                        unit=series.unit,
                        baseline_value=baseline,
                        peak_value=max_val,
                        delta_pct=round(delta_pct, 1),
                        description=desc,
                        labels=series.labels,
                    )
                )

        # 3. Identify Health Degradations
        health_degradations = [
            h for h in telemetry.health_signals
            if h.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
        ]
        health_degradations.sort(key=lambda x: x.timestamp)

        # 4. Identify Unaffected Services
        all_services = {log.service_name for log in telemetry.logs}
        affected_services = {c.service_name for c in error_clusters} | {m.service_name for m in metric_anomalies}
        unaffected = list(all_services - affected_services)

        return CorrelatedTelemetrySummary(
            incident_id=metadata.incident_id,
            affected_service=metadata.affected_service,
            time_window_start=telemetry.time_window_start,
            time_window_end=telemetry.time_window_end,
            total_raw_logs=len(telemetry.logs),
            error_clusters=error_clusters,
            metric_anomalies=metric_anomalies,
            recent_deployments=telemetry.deployments,
            health_degradations=health_degradations,
            unaffected_services=unaffected,
        )

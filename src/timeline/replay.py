"""Generates step-by-step telemetry state replay snapshots for time-scrubbing."""

from __future__ import annotations

from datetime import timedelta

from src.schemas.incident import Incident
from src.schemas.telemetry import HealthStatus, LogLevel
from src.schemas.timeline import IncidentReplaySeries, SystemReplaySnapshot


class IncidentReplayProvider:
    """Discretizes multi-signal telemetry into chronological 1-minute step snapshots."""

    @classmethod
    def generate_replay_series(
        cls,
        incident: Incident,
        interval_seconds: int = 60,
    ) -> IncidentReplaySeries:
        """Discretizes the incident window into ordered SystemReplaySnapshot steps."""
        telemetry = incident.telemetry
        meta = incident.metadata
        svc = meta.affected_service

        start_time = telemetry.time_window_start
        end_time = telemetry.time_window_end

        total_span_sec = max(interval_seconds, int((end_time - start_time).total_seconds()))
        total_steps = (total_span_sec // interval_seconds) + 1

        snapshots: list[SystemReplaySnapshot] = []

        # Index metrics for fast point-in-time lookup
        # Find the primary anomalous metric if available
        primary_series = None
        max_deviation = -1.0
        for s in telemetry.metrics:
            if not s.points:
                continue
            base = s.points[0].value
            peak = max(p.value for p in s.points)
            dev = abs(peak - base)
            if dev > max_deviation:
                max_deviation = dev
                primary_series = s

        # Canonical lifecycle timing
        svc_health = [h for h in telemetry.health_signals if h.service_name == svc]
        mitigation_time = meta.detected_at + timedelta(minutes=5)
        healthy_signal = next(
            (h for h in reversed(svc_health) if h.status == HealthStatus.HEALTHY and h.timestamp > meta.detected_at),
            None,
        )
        if healthy_signal:
            recovery_time = healthy_signal.timestamp
        else:
            recovery_time = max(mitigation_time + timedelta(minutes=1), end_time - timedelta(minutes=1))
        resolved_time = min(end_time, recovery_time + timedelta(minutes=1))

        current_time = start_time
        for step_idx in range(total_steps):
            window_step_end = current_time + timedelta(seconds=interval_seconds)

            # 1. Capture logs in this interval
            interval_logs = [
                l for l in telemetry.logs
                if current_time <= l.timestamp < window_step_end
            ]
            error_logs = [
                l for l in interval_logs
                if l.log_level in (LogLevel.ERROR, LogLevel.FATAL)
            ]
            sample_err = error_logs[0].message if error_logs else None

            # 2. Capture primary metric value closest to current_time
            metric_val: float | None = None
            metric_name: str | None = None
            metric_unit: str | None = None

            if primary_series and primary_series.points:
                # Find point closest to current_time
                closest_pt = min(primary_series.points, key=lambda p: abs((p.timestamp - current_time).total_seconds()))
                metric_val = round(closest_pt.value, 2)
                metric_name = primary_series.metric_name
                metric_unit = primary_series.unit

            # 3. Capture health status at this time
            if current_time >= recovery_time:
                status_str = "HEALTHY"
                lat_p99 = 25.0
                err_rate = 0.0
            else:
                health_pt = next(
                    (h for h in reversed(svc_health) if h.timestamp <= current_time),
                    svc_health[0] if svc_health else None,
                )
                status_str = health_pt.status.value if health_pt else "HEALTHY"
                lat_p99 = health_pt.latency_p99_ms if health_pt else 25.0
                err_rate = health_pt.error_rate_pct if health_pt else 0.0

            # 4. Generate contextual annotation
            annotation = None
            # Check if any deployment at this step
            dep = next((d for d in telemetry.deployments if current_time <= d.timestamp < window_step_end), None)
            if dep:
                annotation = f"Deployment: {dep.service_name} {dep.version} deployed ({dep.change_summary})"
            elif current_time <= meta.detected_at < window_step_end:
                annotation = f"Alert Triggered: {meta.title} (Severity: {meta.severity.value})"
            elif current_time <= mitigation_time < window_step_end:
                annotation = "Remediation Mitigation Executed: Operational fix applied"
            elif current_time <= recovery_time < window_step_end:
                annotation = "Service Health Recovery Verified: Error rate collapsed to 0%"
            elif current_time >= resolved_time:
                annotation = f"Incident Formally Resolved ({meta.incident_id})"
            elif error_logs:
                annotation = f"Error Burst: {len(error_logs)} error logs captured in interval"
            elif status_str == "DEGRADED":
                annotation = "Service degraded: health checks failing"
            elif status_str == "UNHEALTHY":
                annotation = "Service unhealthy: high error rate and latency"

            snapshots.append(
                SystemReplaySnapshot(
                    timestamp=current_time,
                    step_index=step_idx,
                    service_name=svc,
                    health_status=status_str,
                    error_rate_pct=round(err_rate, 2),
                    latency_p99_ms=round(lat_p99, 1),
                    primary_metric_name=metric_name,
                    primary_metric_value=metric_val,
                    primary_metric_unit=metric_unit,
                    active_error_count=len(error_logs),
                    sample_error_log=sample_err,
                    active_annotation=annotation,
                )
            )

            current_time = window_step_end

        return IncidentReplaySeries(
            incident_id=meta.incident_id,
            service_name=svc,
            interval_seconds=interval_seconds,
            total_steps=len(snapshots),
            snapshots=snapshots,
        )

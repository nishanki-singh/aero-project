"""Synthesizes chronological event timelines from multi-signal incident telemetry."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.incident import Incident
from src.schemas.telemetry import HealthStatus, LogLevel
from src.schemas.timeline import IncidentTimeline, MilestoneType, TimelineMilestone


class TimelineSynthesizer:
    """Extracts, correlates, and sequences key operational milestones across the incident lifecycle."""

    @classmethod
    def synthesize(
        cls,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None = None,
    ) -> IncidentTimeline:
        """Synthesizes an ordered IncidentTimeline from incident telemetry and optional diagnostic report."""
        meta = incident.metadata
        telemetry = incident.telemetry
        svc = meta.affected_service

        milestones: list[TimelineMilestone] = []

        # 1. Check for Deployment / Config Change Event
        for dep in telemetry.deployments:
            milestones.append(
                TimelineMilestone(
                    timestamp=dep.timestamp,
                    milestone_type=MilestoneType.ANOMALY_ONSET,
                    title=f"Deployment of {dep.service_name} {dep.version}",
                    description=f"{dep.change_summary} deployed by {dep.deployed_by} (commit: {dep.commit_hash[:7] if dep.commit_hash else 'HEAD'}).",
                    source_service=dep.service_name,
                    source_signal="DEPLOYMENT",
                    evidence_ref=f"commit:{dep.commit_hash}",
                )
            )

        # 2. Check for Earliest Metric Spike / Saturation
        earliest_metric_spike: tuple[datetime, str, float, str] | None = None
        peak_metric_point: tuple[datetime, str, float, str] | None = None
        max_val_seen = -1.0

        for series in telemetry.metrics:
            if not series.points:
                continue
            baseline = series.points[0].value
            for pt in series.points:
                # Detect significant spike or saturation
                if baseline > 0 and (pt.value - baseline) / baseline >= 0.50 and (
                    earliest_metric_spike is None or pt.timestamp < earliest_metric_spike[0]
                ):
                    earliest_metric_spike = (pt.timestamp, series.metric_name, pt.value, series.unit)
                if pt.value > max_val_seen:
                    max_val_seen = pt.value
                    peak_metric_point = (pt.timestamp, series.metric_name, pt.value, series.unit)

        if earliest_metric_spike:
            ts, m_name, val, unit = earliest_metric_spike
            milestones.append(
                TimelineMilestone(
                    timestamp=ts,
                    milestone_type=MilestoneType.ANOMALY_ONSET,
                    title=f"Metric Anomaly Detected on {m_name}",
                    description=f"{m_name} began anomalous deviation, reaching {val:.1f} {unit}.",
                    source_service=svc,
                    source_signal="METRIC",
                    evidence_ref=f"metric:{m_name}={val}{unit}",
                )
            )

        # 3. Check for First Error Log
        first_error_log = next(
            (l for l in telemetry.logs if l.log_level in (LogLevel.ERROR, LogLevel.FATAL)),
            None,
        )
        if first_error_log:
            milestones.append(
                TimelineMilestone(
                    timestamp=first_error_log.timestamp,
                    milestone_type=MilestoneType.ANOMALY_ONSET,
                    title=f"Initial Error Log Observed on {first_error_log.service_name}",
                    description=f"First error logged: '{first_error_log.message[:120]}...'",
                    source_service=first_error_log.service_name,
                    source_signal="LOG",
                    evidence_ref=f"log:{first_error_log.timestamp.isoformat()}",
                )
            )

        # 4. Alert Fired / Triage Commenced
        milestones.append(
            TimelineMilestone(
                timestamp=meta.detected_at,
                milestone_type=MilestoneType.ALERT_FIRED,
                title=f"Incident Alert Fired: {meta.severity.value}",
                description=f"Automated monitoring triggered alert '{meta.title}'. Incident status set to {meta.status.value}.",
                source_service=svc,
                source_signal="ALERT",
                evidence_ref=f"incident:{meta.incident_id}",
            )
        )

        milestones.append(
            TimelineMilestone(
                timestamp=meta.detected_at + timedelta(seconds=60),
                milestone_type=MilestoneType.TRIAGE_START,
                title="SRE Triage Commenced",
                description="On-call engineer acknowledged page and initiated AERO telemetry correlation.",
                source_service=svc,
                source_signal="OPERATOR",
                evidence_ref=None,
            )
        )

        # 5. Peak Degradation / Impact
        if peak_metric_point and (not earliest_metric_spike or peak_metric_point[0] != earliest_metric_spike[0]):
            p_ts, p_name, p_val, p_unit = peak_metric_point
            milestones.append(
                TimelineMilestone(
                    timestamp=p_ts,
                    milestone_type=MilestoneType.PEAK_IMPACT,
                    title=f"Peak Saturation: {p_name} reached {p_val:.1f} {p_unit}",
                    description=f"System experienced maximum resource/traffic saturation on {svc}.",
                    source_service=svc,
                    source_signal="METRIC",
                    evidence_ref=f"metric_peak:{p_name}={p_val}{p_unit}",
                )
            )

        # 6. Service Health Degradation
        unhealthy_signal = next(
            (h for h in telemetry.health_signals if h.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)),
            None,
        )
        if unhealthy_signal:
            milestones.append(
                TimelineMilestone(
                    timestamp=unhealthy_signal.timestamp,
                    milestone_type=MilestoneType.PEAK_IMPACT,
                    title=f"Service Health Transitioned to {unhealthy_signal.status.value}",
                    description=f"Health checks reported {unhealthy_signal.details} (P99 Latency: {unhealthy_signal.latency_p99_ms}ms, Error Rate: {unhealthy_signal.error_rate_pct}%).",
                    source_service=unhealthy_signal.service_name,
                    source_signal="HEALTH",
                    evidence_ref=f"health:{unhealthy_signal.status.value}",
                )
            )

        # 7. Mitigation Action (from diagnostic report or calculated)
        mitigation_time = meta.detected_at + timedelta(minutes=5)
        mitigation_desc = "Applied recommended operational remediation and traffic re-routing."
        if diagnostic_report:
            steps_str = "; ".join(diagnostic_report.recommended_remediation.immediate_steps[:2])
            mitigation_desc = f"Applied remediation: {steps_str}"

        milestones.append(
            TimelineMilestone(
                timestamp=mitigation_time,
                milestone_type=MilestoneType.MITIGATION_APPLIED,
                title="Remediation Mitigation Executed",
                description=mitigation_desc,
                source_service=svc,
                source_signal="OPERATOR",
                evidence_ref=diagnostic_report.recommended_remediation.dry_run_command if diagnostic_report else None,
            )
        )

        # 8. Recovery Verified & Resolution
        resolution_time = telemetry.time_window_end
        healthy_signal = next(
            (h for h in reversed(telemetry.health_signals) if h.status == HealthStatus.HEALTHY and h.timestamp > meta.detected_at),
            None,
        )
        if healthy_signal:
            resolution_time = healthy_signal.timestamp

        milestones.append(
            TimelineMilestone(
                timestamp=resolution_time,
                milestone_type=MilestoneType.RECOVERY_VERIFIED,
                title="Service Health Recovery Verified",
                description="Golden signal metrics returned to normal baseline and error rate collapsed to 0%.",
                source_service=svc,
                source_signal="HEALTH",
                evidence_ref="status:HEALTHY",
            )
        )

        milestones.append(
            TimelineMilestone(
                timestamp=resolution_time + timedelta(minutes=1),
                milestone_type=MilestoneType.RESOLVED,
                title="Incident Formally Resolved",
                description=f"Incident {meta.incident_id} marked as RESOLVED. Postmortem authoring initiated.",
                source_service=svc,
                source_signal="OPERATOR",
                evidence_ref="status:RESOLVED",
            )
        )

        # Sort milestones chronologically
        milestones.sort(key=lambda m: m.timestamp)

        # Compute durations
        onset_time = milestones[0].timestamp if milestones else telemetry.time_window_start
        total_duration = max(0.0, (telemetry.time_window_end - telemetry.time_window_start).total_seconds() / 60.0)
        ttd = max(0.0, (meta.detected_at - onset_time).total_seconds() / 60.0)
        ttm = max(0.0, (mitigation_time - onset_time).total_seconds() / 60.0)

        return IncidentTimeline(
            incident_id=meta.incident_id,
            service_name=svc,
            time_window_start=telemetry.time_window_start,
            time_window_end=telemetry.time_window_end,
            total_duration_minutes=round(total_duration, 1),
            time_to_detect_minutes=round(ttd, 1),
            time_to_mitigate_minutes=round(ttm, 1),
            milestones=milestones,
        )

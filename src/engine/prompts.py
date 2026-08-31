"""Prompt templates and system instructions for AERO Gemini Diagnostic Engine."""

from __future__ import annotations

import json
from typing import Optional
from src.engine.correlator import CorrelatedTelemetrySummary
from src.schemas.incident import Incident


SYSTEM_INSTRUCTION = """You are AERO (AI-Enabled Reliability & Operations), an expert Google Cloud Site Reliability Engineering (SRE) Copilot.
Your objective is to diagnose cloud-native production incidents by performing rigorous causal reasoning over multi-signal telemetry.

CRITICAL ANTI-HALLUCINATION & GROUNDING CONSTRAINTS:
1. Every diagnostic claim, root cause assertion, and supporting evidence item MUST be strictly grounded in the provided telemetry.
2. You MUST cite exact timestamps, verbatim error messages, metric names, and deployment versions directly from the context.
3. You MUST NEVER fabricate log lines, metrics, timestamps, deployment events, or error codes.
4. If an expected signal is absent from the telemetry, state clearly that it was not observed.
5. Distinguish the root-cause trigger from downstream cascading symptoms (e.g. an unindexed query is the trigger; connection pool saturation and HTTP 504 are symptoms).
6. Provide an evidence-backed remediation plan with verification metrics and rollback procedures.
"""


def build_diagnostic_prompt(incident: Incident, summary: CorrelatedTelemetrySummary) -> str:
    """Builds the comprehensive, structured prompt payload for Gemini reasoning."""
    meta = incident.metadata

    # 1. Format Deployments
    deploys_text = "No recent deployments observed in observation window."
    if summary.recent_deployments:
        lines = []
        for d in summary.recent_deployments:
            lines.append(
                f"- [{d.timestamp.isoformat()}] Service: '{d.service_name}', Version: '{d.version}', "
                f"Commit: '{d.commit_hash}', Author: '{d.deployed_by}', Summary: '{d.change_summary}'"
            )
        deploys_text = "\n".join(lines)

    # 2. Format Metric Anomalies
    metrics_text = "No anomalous metric spikes detected."
    if summary.metric_anomalies:
        lines = []
        for m in summary.metric_anomalies:
            labels_str = f" (labels: {json.dumps(m.labels)})" if m.labels else ""
            lines.append(
                f"- Metric: '{m.metric_name}' on service '{m.service_name}'{labels_str}\n"
                f"  Baseline: {m.baseline_value} {m.unit} -> Peak: {m.peak_value} {m.unit} (Delta: {m.delta_pct:+.1f}%)\n"
                f"  Observation: {m.description}"
            )
        metrics_text = "\n".join(lines)

    # 3. Format Error Logs
    logs_text = "No error-level logs captured in observation window."
    if summary.error_clusters:
        lines = []
        for c in summary.error_clusters:
            sample = c.sample_log
            trace_info = f", TraceID: {sample.trace_id}" if sample.trace_id else ""
            lines.append(
                f"- [{sample.timestamp.isoformat()}] [{c.log_level.value}] Service: '{c.service_name}' (Count: {c.count} occurrences)\n"
                f"  Message: \"{sample.message}\"{trace_info}\n"
                f"  Attributes: {json.dumps(sample.attributes)}"
            )
        logs_text = "\n".join(lines)

    # 4. Format Health Signals
    health_text = "All service health checks passing."
    if summary.health_degradations:
        lines = []
        for h in summary.health_degradations:
            lines.append(
                f"- [{h.timestamp.isoformat()}] Service: '{h.service_name}', Status: '{h.status.value}', "
                f"P99 Latency: {h.latency_p99_ms}ms, Error Rate: {h.error_rate_pct}%, Details: '{h.details}'"
            )
        health_text = "\n".join(lines)

    prompt = f"""### INCIDENT CONTEXT
- Incident ID: {meta.incident_id}
- Title: {meta.title}
- Severity: {meta.severity.value}
- Affected Service: {meta.affected_service}
- Impact Summary: {meta.impact_summary}
- Detected At: {meta.detected_at.isoformat()}
- Observation Window: {summary.time_window_start.isoformat()} to {summary.time_window_end.isoformat()}
- Total Raw Logs Analyzed: {summary.total_raw_logs}

---

### CORRELATED TELEMETRY EVIDENCE

#### 1. Recent Deployment & Configuration Events:
{deploys_text}

#### 2. Metric Anomalies & Golden Signals:
{metrics_text}

#### 3. Clustered Error Logs & Stack Traces:
{logs_text}

#### 4. Service Health State Transitions:
{health_text}

---

### DIAGNOSTIC INSTRUCTIONS:
1. Analyze the correlated evidence to identify the primary root cause and trigger event.
2. Formulate a structured diagnostic report conforming strictly to the requested JSON schema.
3. In `supporting_evidence`, cite ONLY timestamps, messages, and metrics that appear verbatim in the telemetry above.
4. Calculate a confidence score (0.0 to 1.0) and confidence rating (HIGH, MEDIUM, LOW) with clear justification.
5. Formulate a step-by-step remediation plan with dry-run commands and recovery verification metrics.
"""
    return prompt

"""Prompt templates and context builders for Grounded SRE Copilot."""

from __future__ import annotations

from src.config import config
from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.incident import Incident
from src.schemas.timeline import IncidentTimeline

COPILOT_SYSTEM_INSTRUCTION = """You are AERO (AI-Enabled Reliability & Operations) SRE Copilot, an expert Google Cloud Site Reliability Engineering assistant.
Your job is to answer SRE questions strictly grounded in the currently active incident's multi-signal telemetry.

CRITICAL GROUNDING & SAFETY CONSTRAINTS:
1. Every answer MUST be partitioned into three explicit structural categories:
   - OBSERVED EVIDENCE: Facts directly present in telemetry, logs, metrics, deployment records, or health checks.
   - DERIVED INFERENCE: Causal reasoning, deductions, and hypotheses derived from the observed facts.
   - SRE RECOMMENDATION: Actionable verification or operational advice for on-call engineers (advisory-only).
2. DO NOT claim an inference or recommendation is an observed telemetry fact.
3. DO NOT fabricate metrics, log entries, timestamps, or deployments.
4. If the user asks about an event or component not present in the active incident data, you MUST state clearly that the evidence is unavailable in the current telemetry window.
5. NEVER suggest executing automated infrastructure mutation; all remediation is simulated or advisory.
"""


def build_copilot_prompt(
    incident: Incident,
    diagnostic_report: AeroDiagnosticReport | None,
    timeline: IncidentTimeline | None,
    question: str,
) -> str:
    """Builds the comprehensive active incident context payload for Copilot reasoning."""
    meta = incident.metadata
    telemetry = incident.telemetry

    # 1. Incident Metadata
    incident_section = (
        f"INCIDENT CONTEXT:\n"
        f"- Incident ID: {meta.incident_id}\n"
        f"- Affected Service: {meta.affected_service}\n"
        f"- Environment: {config.environment}\n"
        f"- Severity: {meta.severity.value}\n"
        f"- Detected At: {meta.detected_at.isoformat()}\n"
        f"- Title: {meta.title}\n"
        f"- Summary: {meta.impact_summary}\n"
    )

    # 2. Metric Series Summary
    metric_lines = []
    for m in telemetry.metrics:
        points = m.points
        if points:
            vals = [p.value for p in points]
            min_v, max_v = min(vals), max(vals)
            metric_lines.append(
                f"- Metric: '{m.metric_name}' (Service: {m.service_name}, Unit: {m.unit}) -> "
                f"Min: {min_v:.2f}, Max: {max_v:.2f}, Latest: {vals[-1]:.2f}"
            )
    metrics_section = "METRICS:\n" + ("\n".join(metric_lines) if metric_lines else "No metric series recorded.")

    # 3. Key Log Messages (Errors & Warnings)
    log_lines = []
    for log in telemetry.logs:
        if log.log_level.value in ("ERROR", "FATAL", "WARN"):
            log_lines.append(f"- [{log.timestamp.isoformat()}] [{log.log_level.value}] [{log.service_name}] {log.message}")
    logs_section = "ERROR/WARN LOGS:\n" + ("\n".join(log_lines[:25]) if log_lines else "No critical logs recorded.")

    # 4. Deployments / Changes
    deploy_lines = []
    for d in telemetry.deployments:
        deploy_lines.append(
            f"- [{d.timestamp.isoformat()}] Service: {d.service_name}, Version: {d.version}, "
            f"Commit: {d.commit_hash}, Summary: {d.change_summary}"
        )
    deploys_section = "RECENT DEPLOYMENTS:\n" + ("\n".join(deploy_lines) if deploy_lines else "No deployment events recorded.")

    # 5. Diagnostic RCA & 5-Whys if available
    diag_section = "DIAGNOSTIC REASONING:\n"
    if diagnostic_report:
        rc = diagnostic_report.probable_root_cause
        diag_section += (
            f"- Probable Root Cause: {rc.title} ({rc.category})\n"
            f"- Trigger Event: {rc.trigger_event}\n"
            f"- Causal Description: {rc.description}\n"
        )
        if diagnostic_report.five_whys:
            diag_section += "Five Whys:\n"
            for fw in diagnostic_report.five_whys:
                evidence_note = f" (Evidence: {fw.evidence_ref})" if fw.evidence_ref else " (Inferred)"
                diag_section += f"  {fw.level}. Why: {fw.why} -> Because: {fw.because}{evidence_note}\n"
    else:
        diag_section += "Diagnostic RCA not yet synthesized."

    # 6. Timeline Milestones if available
    timeline_section = "TIMELINE MILESTONES:\n"
    if timeline and timeline.milestones:
        for m in timeline.milestones:
            timeline_section += f"- [{m.timestamp.isoformat()}] [{m.milestone_type.value}] {m.title}: {m.description}\n"
    else:
        timeline_section += "Timeline not synthesized."

    # Full prompt assembly
    prompt = f"""{incident_section}

{metrics_section}

{logs_section}

{deploys_section}

{diag_section}

{timeline_section}

USER QUESTION:
"{question}"

Generate a structured JSON response matching the following schema:
{{
  "answer": "<concise markdown summary>",
  "evidence": [
    {{
      "signal_type": "LOG" | "METRIC" | "DEPLOYMENT" | "HEALTH",
      "source": "<originating service or metric name>",
      "description": "<verbatim fact from telemetry>",
      "metric_name": "<name if metric>",
      "log_snippet": "<verbatim text if log>",
      "confidence": 1.0
    }}
  ],
  "inferences": [
    "<causal deduction based on evidence>"
  ],
  "recommendations": [
    "<operational next step or verification target>"
  ],
  "confidence": 0.95
}}
"""
    return prompt

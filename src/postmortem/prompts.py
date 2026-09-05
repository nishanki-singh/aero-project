"""Prompt templates and system instructions for Google SRE standard postmortem synthesis."""

from __future__ import annotations

from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.incident import Incident
from src.schemas.timeline import IncidentTimeline

POSTMORTEM_SYSTEM_INSTRUCTION = """You are AERO (AI-Enabled Reliability & Operations), an expert Google Cloud Site Reliability Engineering (SRE) Postmortem Architect.
Your task is to author a blameless, rigorous, and publication-ready incident postmortem conforming strictly to Google SRE postmortem best practices.

CORE REQUIREMENTS:
1. Blameless Culture: Focus on system design gaps, missing guardrails, and architectural resilience rather than individual human error.
2. Five-Whys Deep Causal Chain: Construct an exact 5-level hierarchical causal chain linking surface symptoms back to fundamental system/architecture deficiencies.
3. Quantified Impact: Detail service disruption, affected workflows, and duration.
4. Actionable Preventative Items: Provide prioritized action items (P0, P1, P2) with clear owners, estimated effort, and verification criteria to ensure the failure cannot reoccur.
5. Grounded Consistency: Ensure all facts, timestamps, metric names, and remediation actions align strictly with the diagnostic report and incident timeline.
"""


def build_postmortem_prompt(
    incident: Incident,
    diagnostic_report: AeroDiagnosticReport,
    timeline: IncidentTimeline,
) -> str:
    """Builds the comprehensive postmortem prompt payload for Gemini."""
    meta = incident.metadata
    rc = diagnostic_report.probable_root_cause
    remed = diagnostic_report.recommended_remediation

    # Format timeline milestones
    milestone_lines = []
    for m in timeline.milestones:
        milestone_lines.append(
            f"- [{m.timestamp.isoformat()}] [{m.milestone_type.value}] {m.title}: {m.description}"
        )
    milestones_text = "\n".join(milestone_lines)

    # Format evidence
    evidence_lines = []
    for ev in diagnostic_report.supporting_evidence:
        evidence_lines.append(
            f"- [{ev.signal_type.value}] ({ev.timestamp.isoformat()}) {ev.source}: {ev.content}"
        )
    evidence_text = "\n".join(evidence_lines)

    # Format remediation
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(remed.immediate_steps))

    prompt = f"""### INCIDENT CONTEXT
- Incident ID: {meta.incident_id}
- Title: {meta.title}
- Service: {meta.affected_service}
- Severity: {meta.severity.value}
- Total Duration: {timeline.total_duration_minutes:.1f} minutes
- Time to Detect (TTD): {timeline.time_to_detect_minutes} minutes
- Time to Mitigate (TTM): {timeline.time_to_mitigate_minutes} minutes

---

### DIAGNOSTIC FINDINGS (ROOT CAUSE ANALYSIS)
- Category: {rc.category}
- Title: {rc.title}
- Trigger Event: {rc.trigger_event}
- Description: {rc.description}
- Diagnostic Confidence: {diagnostic_report.confidence_level.score * 100:.0f}% ({diagnostic_report.confidence_level.rating.value})

#### Cited Supporting Evidence:
{evidence_text}

#### Remediation Actions Performed:
{steps_text}
- Verification Metric: {remed.verification_metric}
- Rollback Plan: {remed.rollback_plan}

---

### CHRONOLOGICAL INCIDENT TIMELINE
{milestones_text}

---

### POSTMORTEM AUTHORING INSTRUCTIONS:
1. Generate a publication-ready postmortem conforming to the AeroPostmortem JSON schema.
2. Synthesize an Executive Summary for VP/Director engineering leadership.
3. Formulate a 5-level Five-Whys causal hierarchy drilling from the immediate symptom down to root architecture/process gaps.
4. Define at least 3 concrete preventative Action Items (P0 Blocker, P1 High Priority, P2 Medium Priority) with assigned owners.
5. Capture Lessons Learned: what went well, what went wrong, and where we got lucky.
"""
    return prompt

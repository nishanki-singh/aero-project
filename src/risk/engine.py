"""Deterministic Risk Analysis Engine for AERO Pre-Deployment Risk Advisor."""

from __future__ import annotations

from src.risk import rules
from src.schemas.incident import Incident
from src.schemas.risk import (
    ProposedChange,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    RiskFinding,
    RiskSeverity,
)


class DeterministicRiskEngine:
    """Offline, deterministic risk evaluation engine analyzing proposed deployment/config changes."""

    def evaluate(
        self,
        change: ProposedChange,
        incident: Incident | None = None,
    ) -> RiskAnalysisResponse:
        """Run all deterministic risk checks against proposed change and optional incident telemetry."""
        all_findings: list[RiskFinding] = []

        # Run all modular rule evaluators
        all_findings.extend(rules.check_resource_limits(change, incident))
        all_findings.extend(rules.check_database_pool(change))
        all_findings.extend(rules.check_timeouts_and_dependencies(change))
        all_findings.extend(rules.check_health_and_readiness(change))
        all_findings.extend(rules.check_rollback_strategy(change))
        all_findings.extend(rules.check_dangerous_config(change))
        all_findings.extend(rules.check_config_drift(change, incident))
        all_findings.extend(rules.check_critical_service(change))

        # Check if input was insufficient
        insufficient_findings = rules.check_insufficient_input(change)
        is_insufficient = len(insufficient_findings) > 0 and len(all_findings) == 0
        if is_insufficient:
            all_findings.extend(insufficient_findings)

        # Calculate aggregated risk score
        raw_score = sum(f.score_impact for f in all_findings)
        risk_score = min(100, max(0, raw_score))

        # Determine overall severity
        has_critical = any(f.severity == RiskSeverity.CRITICAL for f in all_findings)
        has_high = any(f.severity == RiskSeverity.HIGH for f in all_findings)
        has_medium = any(f.severity == RiskSeverity.MEDIUM for f in all_findings)

        if has_critical or risk_score >= 70:
            overall_severity = RiskSeverity.CRITICAL
        elif has_high or risk_score >= 45:
            overall_severity = RiskSeverity.HIGH
        elif has_medium or risk_score >= 20:
            overall_severity = RiskSeverity.MEDIUM
        else:
            overall_severity = RiskSeverity.LOW

        # Safe to deploy invariant: Score < 40 and severity in [LOW, MEDIUM]
        is_safe_to_deploy = risk_score < 40 and overall_severity in [RiskSeverity.LOW, RiskSeverity.MEDIUM]

        # Aggregate observed facts
        observed_facts: list[str] = []
        for f in all_findings:
            for fact in f.observed_facts:
                if fact not in observed_facts:
                    observed_facts.append(fact)

        # Aggregate preventive recommendations
        recommendations: list[str] = []
        for f in all_findings:
            for rec in f.recommendations:
                if rec not in recommendations:
                    recommendations.append(rec)

        # Build explanation
        if is_insufficient:
            explanation = (
                "Sparse change input provided. Heuristic analysis performed without full parameter specs. "
                "Provide detailed resource limits, timeouts, and probe settings for deep risk evaluation."
            )
        elif overall_severity == RiskSeverity.CRITICAL:
            critical_titles = [f.title for f in all_findings if f.severity == RiskSeverity.CRITICAL]
            explanation = (
                f"DEPLOYMENT BLOCKED: Critical risk anti-patterns detected ({', '.join(critical_titles)}). "
                "These changes pose an immediate risk of service disruption or pod eviction."
            )
        elif overall_severity == RiskSeverity.HIGH:
            high_titles = [f.title for f in all_findings if f.severity == RiskSeverity.HIGH]
            explanation = (
                f"HIGH RISK CHANGE: Significant stability risks identified ({', '.join(high_titles)}). "
                "Recommended to apply preventive guardrails before production rollout."
            )
        elif overall_severity == RiskSeverity.MEDIUM:
            explanation = (
                "MODERATE RISK: Change contains cautionary signals (e.g. tier-1 blast radius or rollback omissions). "
                "Proceed with canary rollout and active telemetry monitoring."
            )
        else:
            explanation = "LOW RISK: Proposed change adheres to production safety guidelines and resource constraints."

        return RiskAnalysisResponse(
            overall_severity=overall_severity,
            risk_score=risk_score,
            is_safe_to_deploy=is_safe_to_deploy,
            findings=all_findings,
            observed_facts_summary=observed_facts,
            preventive_recommendations=recommendations,
            rule_evaluation_count=8,
            scenario_context_applied=incident is not None,
            insufficient_data=is_insufficient,
            explanation=explanation,
        )

    def analyze_request(
        self,
        request: RiskAnalysisRequest,
        incident: Incident | None = None,
    ) -> RiskAnalysisResponse:
        """Helper to evaluate a full RiskAnalysisRequest."""
        return self.evaluate(request.proposed_change, incident)

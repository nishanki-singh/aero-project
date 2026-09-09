"""Deterministic Risk Analysis Engine for AERO Pre-Deployment Risk Advisor.

Evaluates proposed deployment/configuration changes against:
1. 18 Generic SRE deployment safety rules
2. Incident diagnosis and telemetry evidence (recurrence prevention)
3. AERO mitigation recommendations
"""

from __future__ import annotations

from src.risk import rules
from src.schemas.incident import Incident
from src.schemas.risk import (
    DiagnosisContext,
    EvaluatedChangeSummary,
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
        diag_context: DiagnosisContext | None = None,
    ) -> RiskAnalysisResponse:
        """Run all deterministic risk checks against proposed change and optional incident telemetry/diagnosis."""
        generic_findings: list[RiskFinding] = []

        # 1. Run all 8 modular generic rule evaluators (18 deterministic rules)
        generic_findings.extend(rules.check_resource_limits(change, incident))
        generic_findings.extend(rules.check_database_pool(change))
        generic_findings.extend(rules.check_timeouts_and_dependencies(change))
        generic_findings.extend(rules.check_health_and_readiness(change))
        generic_findings.extend(rules.check_rollback_strategy(change))
        generic_findings.extend(rules.check_dangerous_config(change))
        generic_findings.extend(rules.check_config_drift(change, incident))
        generic_findings.extend(rules.check_critical_service(change))

        # Check if input was insufficient
        insufficient_findings = rules.check_insufficient_input(change)
        is_insufficient = len(insufficient_findings) > 0 and len(generic_findings) == 0
        if is_insufficient:
            generic_findings.extend(insufficient_findings)

        # 2. Run Diagnosis-Aware Prevention Rules (RISK-PREV-*)
        (
            prevention_findings,
            diagnosis_alignment,
            predicted_recurrence,
            evidence_used,
        ) = rules.evaluate_diagnosis_prevention_rules(change, incident, diag_context)

        # 3. Combine findings
        all_findings = generic_findings + prevention_findings

        # Calculate aggregated risk score
        raw_score = sum(f.score_impact for f in all_findings)
        risk_score = min(100, max(0, raw_score))

        # Determine overall deployment risk severity
        has_critical = any(f.severity == RiskSeverity.CRITICAL for f in all_findings)
        has_high = any(f.severity == RiskSeverity.HIGH for f in all_findings)
        has_medium = any(f.severity == RiskSeverity.MEDIUM for f in all_findings)

        if has_critical or risk_score >= 70:
            overall_severity = RiskSeverity.CRITICAL
            decision = "BLOCKED"
            is_safe_to_deploy = False
        elif has_high or risk_score >= 45:
            overall_severity = RiskSeverity.HIGH
            decision = "HIGH_RISK"
            is_safe_to_deploy = False
        elif has_medium or risk_score >= 20:
            overall_severity = RiskSeverity.MEDIUM
            decision = "WARNING"
            is_safe_to_deploy = risk_score < 40
        else:
            overall_severity = RiskSeverity.LOW
            decision = "SAFE"
            is_safe_to_deploy = True

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

        # Build evaluated change summary
        params = change.parameters or {}
        evaluated_change = EvaluatedChangeSummary(
            service=change.service or params.get("service", ""),
            change_type=change.change_type,
            description=change.description,
            environment=change.environment,
            memory_limit_mb=rules._get_val(change, "memory_limit_mb", "memory_limit"),
            memory_request_mb=rules._get_val(change, "memory_request_mb", "memory_request"),
            cpu_limit=rules._get_val(change, "cpu_limit_cores", "cpu_limit"),
            concurrency=rules._get_val(change, "concurrency", "worker_count", "workers"),
            pool_max=rules._get_val(change, "pool_max", "pool_max_size", "db_pool_size"),
            timeout_seconds=rules._get_val(change, "timeout_seconds"),
            image_tag=rules._get_val(change, "image_tag"),
            rollback_plan=change.rollback_plan or rules._get_val(change, "rollback_version"),
            debug_mode=rules._get_val(change, "debug_mode") is True,
            log_level=rules._get_val(change, "log_level"),
            readiness_probe_enabled=rules._get_val(change, "readiness_probe_enabled") is not False,
            parameters=params,
        )

        # Build high-level narrative explanation
        if is_insufficient:
            explanation = (
                "Sparse change input provided. Heuristic analysis performed without full parameter specs. "
                "Provide detailed resource limits, timeouts, and probe settings for deep risk evaluation."
            )
        elif overall_severity == RiskSeverity.CRITICAL:
            crit_reasons = [f.title for f in all_findings if f.severity == RiskSeverity.CRITICAL]
            explanation = (
                f"DEPLOYMENT BLOCKED: Critical risk anti-patterns detected ({'; '.join(crit_reasons[:2])}). "
                "The proposed change fails pre-deployment safety gates and creates immediate outage or recurrence risk."
            )
        elif overall_severity == RiskSeverity.HIGH:
            high_reasons = [f.title for f in all_findings if f.severity == RiskSeverity.HIGH]
            explanation = (
                f"HIGH RISK DEPLOYMENT: Significant stability concerns identified ({'; '.join(high_reasons[:2])}). "
                "Deploying this change risks recreating the diagnosed failure mode or introducing cascading regressions."
            )
        elif overall_severity == RiskSeverity.MEDIUM:
            explanation = (
                "WARNING: Proposed change contains cautionary signals (e.g. tier-1 blast radius or rollback omissions). "
                "Proceed with canary rollout and active telemetry monitoring."
            )
        else:
            explanation = (
                "SAFE TO DEPLOY: Proposed change satisfies all generic SRE safety constraints and aligns with "
                "incident prevention recommendations. Low recurrence risk."
            )

        total_rules = 8 + 5  # 8 generic categories (18 rules) + 5 prevention rules

        return RiskAnalysisResponse(
            overall_severity=overall_severity,
            risk_score=risk_score,
            is_safe_to_deploy=is_safe_to_deploy,
            decision=decision,
            findings=all_findings,
            generic_findings=generic_findings,
            prevention_findings=prevention_findings,
            diagnosis_alignment=diagnosis_alignment,
            predicted_recurrence=predicted_recurrence,
            evaluated_change=evaluated_change,
            evidence_used=evidence_used,
            observed_facts_summary=observed_facts,
            preventive_recommendations=recommendations,
            rule_evaluation_count=total_rules,
            scenario_context_applied=incident is not None,
            insufficient_data=is_insufficient,
            explanation=explanation,
        )

    def analyze_request(
        self,
        request: RiskAnalysisRequest,
        incident: Incident | None = None,
        diagnosis_context: DiagnosisContext | None = None,
    ) -> RiskAnalysisResponse:
        """Helper to evaluate a full RiskAnalysisRequest."""
        diag_ctx = request.diagnosis_context or diagnosis_context
        return self.evaluate(request.proposed_change, incident, diag_ctx)

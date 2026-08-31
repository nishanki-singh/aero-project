"""Quantitative AI evaluation engine for evaluating diagnostic accuracy and evidence grounding."""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.engine.diagnostic_engine import BaseDiagnosticEngine
from src.engine.grounding_verifier import GroundingVerificationResult, GroundingVerifier
from src.schemas.diagnostic import AeroDiagnosticReport, SignalType
from src.schemas.ground_truth import BenchmarkScenarioBundle, GroundTruthScenario


class ScenarioEvaluationResult(BaseModel):
    """Detailed quantitative evaluation score for a single incident benchmark scenario."""
    scenario_id: str
    scenario_name: str
    category: str
    affected_service: str
    duration_sec: float

    # Core Metrics
    root_cause_category_match: bool
    root_cause_accuracy: float = Field(..., ge=0.0, le=1.0, description="RCA score (0.0 or 1.0).")
    grounding_recall: float = Field(..., ge=0.0, le=1.0, description="Proportion of mandatory ground-truth signals cited.")
    grounding_precision: float = Field(..., ge=0.0, le=1.0, description="Proportion of cited evidence grounded in telemetry.")
    hallucination_rate: float = Field(..., ge=0.0, le=1.0, description="Proportion of cited evidence not found in telemetry.")
    remediation_score: float = Field(..., ge=0.0, le=1.0, description="Coverage of expected mitigation key actions.")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite evaluation score.")
    is_benchmark_passed: bool = Field(..., description="Whether this scenario passed benchmark criteria.")

    diagnostic_report: AeroDiagnosticReport
    grounding_verification: GroundingVerificationResult


class BenchmarkEvaluationReport(BaseModel):
    """Aggregate benchmark evaluation summary across all evaluated scenarios."""
    timestamp: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    mean_root_cause_accuracy: float
    mean_grounding_recall: float
    mean_grounding_precision: float
    mean_hallucination_rate: float
    mean_remediation_score: float
    mean_overall_score: float
    total_duration_sec: float
    all_passed: bool
    results: List[ScenarioEvaluationResult] = Field(default_factory=list)


class IncidentEvaluator:
    """Evaluates an AI Diagnostic Engine's output against known ground-truth benchmark scenarios."""

    @classmethod
    def evaluate_scenario(
        cls,
        bundle: BenchmarkScenarioBundle,
        engine: BaseDiagnosticEngine,
    ) -> ScenarioEvaluationResult:
        """Executes diagnosis and scores output against scenario ground truth."""
        gt = bundle.ground_truth
        incident = bundle.incident

        start_time = time.perf_counter()
        report = engine.diagnose(incident)
        duration_sec = round(time.perf_counter() - start_time, 3)

        # 1. Evaluate Grounding & Hallucination Guardrail
        grounding_result = GroundingVerifier.verify(report, incident)

        # 2. Evaluate Root Cause Accuracy (Taxonomy Category Match)
        category_match = (
            report.probable_root_cause.category.strip().upper()
            == gt.expected_root_cause_category.strip().upper()
        )
        rca_score = 1.0 if category_match else 0.0

        # 3. Evaluate Grounding Recall (Did model cite all mandatory ground truth signals?)
        mandatory_signals = [ev for ev in gt.expected_evidence_signals if ev.is_mandatory]
        found_mandatory = 0

        for m_ev in mandatory_signals:
            pattern_lower = m_ev.pattern.lower()
            cited = False
            for c_ev in report.supporting_evidence:
                if (
                    pattern_lower in c_ev.content.lower()
                    or pattern_lower in c_ev.source.lower()
                ):
                    cited = True
                    break
            if cited:
                found_mandatory += 1

        grounding_recall = (
            (found_mandatory / len(mandatory_signals)) if mandatory_signals else 1.0
        )

        # 4. Evaluate Remediation Score
        expected_actions = gt.expected_remediation.key_actions
        remed_text = " ".join(report.recommended_remediation.immediate_steps).lower()
        matched_actions = sum(
            1 for act in expected_actions
            if any(token in remed_text for token in act.lower().split() if len(token) > 4)
        )
        remediation_score = (
            (matched_actions / len(expected_actions)) if expected_actions else 1.0
        )

        # 5. Compute Weighted Overall Score
        # Weights: RCA = 40%, Grounding Recall = 30%, Grounding Precision = 15%, Remediation = 15%
        overall_score = (
            rca_score * 0.40
            + grounding_recall * 0.30
            + grounding_result.grounding_precision * 0.15
            + remediation_score * 0.15
        )

        # Benchmark criteria: RCA == 1.0, Grounding Recall >= 0.8, Hallucination Rate <= 0.05
        passed = (
            rca_score == 1.0
            and grounding_recall >= 0.80
            and grounding_result.hallucination_rate <= 0.05
        )

        return ScenarioEvaluationResult(
            scenario_id=gt.scenario_id,
            scenario_name=gt.scenario_name,
            category=gt.category,
            affected_service=gt.affected_service,
            duration_sec=duration_sec,
            root_cause_category_match=category_match,
            root_cause_accuracy=rca_score,
            grounding_recall=round(grounding_recall, 4),
            grounding_precision=grounding_result.grounding_precision,
            hallucination_rate=grounding_result.hallucination_rate,
            remediation_score=round(remediation_score, 4),
            overall_score=round(overall_score, 4),
            is_benchmark_passed=passed,
            diagnostic_report=report,
            grounding_verification=grounding_result,
        )

    @classmethod
    def evaluate_benchmark_suite(
        cls,
        bundles: List[BenchmarkScenarioBundle],
        engine: BaseDiagnosticEngine,
    ) -> BenchmarkEvaluationReport:
        """Evaluates an entire suite of benchmark scenarios."""
        from datetime import datetime, timezone

        start_time = time.perf_counter()
        results: List[ScenarioEvaluationResult] = []

        for b in bundles:
            res = cls.evaluate_scenario(b, engine)
            results.append(res)

        total_duration = round(time.perf_counter() - start_time, 3)
        total = len(results)
        passed = sum(1 for r in results if r.is_benchmark_passed)

        mean_rca = sum(r.root_cause_accuracy for r in results) / total if total > 0 else 0.0
        mean_recall = sum(r.grounding_recall for r in results) / total if total > 0 else 0.0
        mean_precision = sum(r.grounding_precision for r in results) / total if total > 0 else 0.0
        mean_hallucination = sum(r.hallucination_rate for r in results) / total if total > 0 else 0.0
        mean_remediation = sum(r.remediation_score for r in results) / total if total > 0 else 0.0
        mean_overall = sum(r.overall_score for r in results) / total if total > 0 else 0.0

        return BenchmarkEvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_scenarios=total,
            passed_scenarios=passed,
            failed_scenarios=total - passed,
            mean_root_cause_accuracy=round(mean_rca, 4),
            mean_grounding_recall=round(mean_recall, 4),
            mean_grounding_precision=round(mean_precision, 4),
            mean_hallucination_rate=round(mean_hallucination, 4),
            mean_remediation_score=round(mean_remediation, 4),
            mean_overall_score=round(mean_overall, 4),
            total_duration_sec=total_duration,
            all_passed=(passed == total and total > 0),
            results=results,
        )

"""Unit tests for the quantitative evaluation framework."""

from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.engine.diagnostic_engine import MockDiagnosticEngine
from src.evaluation.evaluator import IncidentEvaluator


def test_evaluator_scores_all_benchmark_scenarios():
    """Verifies that IncidentEvaluator achieves 100% benchmark criteria on mock engine."""
    engine = MockDiagnosticEngine()
    bundles = [gen_fn(seed=42) for gen_fn in BENCHMARK_SCENARIOS.values()]

    report = IncidentEvaluator.evaluate_benchmark_suite(bundles, engine)

    assert report.total_scenarios == 5
    assert report.passed_scenarios == 5
    assert report.failed_scenarios == 0
    assert report.all_passed is True

    # Check metrics
    assert report.mean_root_cause_accuracy == 1.0  # 100% RCA accuracy
    assert report.mean_grounding_recall >= 0.85
    assert report.mean_grounding_precision == 1.0
    assert report.mean_hallucination_rate == 0.0  # 0% hallucinations
    assert report.mean_remediation_score >= 0.80
    assert report.mean_overall_score >= 0.90

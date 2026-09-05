"""CLI runner for executing quantitative AI diagnostic evaluation across benchmark scenarios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.config import config
from src.engine.diagnostic_engine import (
    MockDiagnosticEngine,
    VertexAiDiagnosticEngine,
)
from src.evaluation.evaluator import (
    BenchmarkEvaluationReport,
    IncidentEvaluator,
)
from src.schemas.ground_truth import BenchmarkScenarioBundle


def run_benchmark_evaluation(
    use_live_vertex: bool = False,
    scenario_filter: str | None = None,
    seed: int = 42,
    output_json: str | None = None,
) -> BenchmarkEvaluationReport:
    """Executes the AI diagnostic evaluation pipeline across benchmark scenarios."""
    engine = VertexAiDiagnosticEngine() if use_live_vertex else MockDiagnosticEngine()
    engine_name = f"Vertex AI Gemini ({config.reasoning_model})" if use_live_vertex else "Deterministic Mock Engine"

    print("\n" + "=" * 90)
    print("[AERO] AI DIAGNOSTIC BENCHMARK EVALUATION")
    print(f"[AERO] Provider: {engine_name} | Random Seed: {seed}")
    print("=" * 90)

    # 1. Load Scenarios
    bundles: list[BenchmarkScenarioBundle] = []
    scenarios_to_run = (
        {scenario_filter: BENCHMARK_SCENARIOS[scenario_filter]}
        if scenario_filter and scenario_filter in BENCHMARK_SCENARIOS
        else BENCHMARK_SCENARIOS
    )

    if scenario_filter and scenario_filter not in BENCHMARK_SCENARIOS:
        print(f"[ERROR] Unknown scenario '{scenario_filter}'. Available: {list(BENCHMARK_SCENARIOS.keys())}")
        sys.exit(1)

    for gen_fn in scenarios_to_run.values():
        bundle = gen_fn(seed=seed)
        bundles.append(bundle)

    # 2. Run Evaluation
    report = IncidentEvaluator.evaluate_benchmark_suite(bundles, engine)

    # 3. Print Results Table
    print("\nSCENARIO SCORECARD:")
    print("-" * 115)
    header = (
        f"{'Scenario ID':<18} | {'Service':<15} | {'RCA':<6} | {'Recall':<8} | "
        f"{'Precision':<10} | {'Halluc%':<8} | {'Remed%':<8} | {'Overall':<8} | {'Status'}"
    )
    print(header)
    print("-" * 115)

    for res in report.results:
        rca_str = "PASS" if res.root_cause_category_match else "FAIL"
        recall_pct = f"{res.grounding_recall * 100:.0f}%"
        prec_pct = f"{res.grounding_precision * 100:.0f}%"
        halluc_pct = f"{res.hallucination_rate * 100:.1f}%"
        remed_pct = f"{res.remediation_score * 100:.0f}%"
        score_pct = f"{res.overall_score * 100:.1f}%"
        status_str = "[PASS]" if res.is_benchmark_passed else "[FAIL]"

        row = (
            f"{res.scenario_id:<18} | {res.affected_service:<15} | {rca_str:<6} | {recall_pct:<8} | "
            f"{prec_pct:<10} | {halluc_pct:<8} | {remed_pct:<8} | {score_pct:<8} | {status_str}"
        )
        print(row)

    print("-" * 115)
    print("\nBENCHMARK AGGREGATE SUMMARY:")
    print(f"- Total Scenarios Evaluated:     {report.total_scenarios}")
    print(f"- Benchmark Passed:             {report.passed_scenarios} / {report.total_scenarios} ({report.passed_scenarios/report.total_scenarios*100:.0f}%)")
    print(f"- Mean Root Cause Accuracy:     {report.mean_root_cause_accuracy * 100:.1f}% (Target: >= 85%)")
    print(f"- Mean Grounding Recall:        {report.mean_grounding_recall * 100:.1f}% (Target: >= 90%)")
    print(f"- Mean Grounding Precision:     {report.mean_grounding_precision * 100:.1f}% (Target: >= 95%)")
    print(f"- Mean Hallucination Rate:      {report.mean_hallucination_rate * 100:.2f}% (Target: <= 2.0%)")
    print(f"- Mean Remediation Score:       {report.mean_remediation_score * 100:.1f}% (Target: >= 80%)")
    print(f"- Mean Overall Composite Score: {report.mean_overall_score * 100:.1f}%")
    print(f"- Total Execution Time:         {report.total_duration_sec:.3f}s")
    print("=" * 90 + "\n")

    # 4. Optional JSON Export
    if output_json:
        out_file = Path(output_json)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"[AERO] Detailed evaluation report saved to {out_file.resolve()}\n")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="AERO AI Diagnostic Benchmark Evaluation CLI")
    parser.add_argument("--live", action="store_true", help="Execute evaluation against live Vertex AI Gemini endpoint")
    parser.add_argument("--scenario", type=str, default=None, help="Specific scenario name to evaluate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for benchmark scenarios")
    parser.add_argument("--output-json", type=str, default=None, help="Export evaluation report JSON to file")

    args = parser.parse_args()
    report = run_benchmark_evaluation(
        use_live_vertex=args.live,
        scenario_filter=args.scenario,
        seed=args.seed,
        output_json=args.output_json,
    )

    if not report.all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

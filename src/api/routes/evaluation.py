"""Benchmark evaluation suite routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import EvaluationRequest
from src.api.service import AeroService
from src.evaluation.evaluator import BenchmarkEvaluationReport

router = APIRouter(prefix="/api/evaluate", tags=["Benchmark Evaluation"])


@router.post("", response_model=BenchmarkEvaluationReport, summary="Execute benchmark suite evaluation")
def evaluate_benchmark(req: EvaluationRequest) -> BenchmarkEvaluationReport:
    """Runs automated quantitative evaluation suite across synthetic scenarios."""
    return AeroService.evaluate_benchmark(
        scenario_keys=req.scenario_keys,
        provider=req.provider or "mock",
        seed=req.seed,
    )

"""Service and orchestration layer decoupling FastAPI routes from intelligence engines."""

from __future__ import annotations

import time

from src.api.schemas import (
    ConfigResponse,
    DiagnoseResponse,
    HealthResponse,
    PostmortemResponse,
    ScenarioSummaryResponse,
)
from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.config import config
from src.engine.diagnostic_engine import get_diagnostic_engine
from src.engine.grounding_verifier import GroundingVerifier
from src.evaluation.evaluator import BenchmarkEvaluationReport, IncidentEvaluator
from src.postmortem.engine import get_postmortem_engine
from src.postmortem.exporter import PostmortemExporter
from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.ground_truth import BenchmarkScenarioBundle
from src.schemas.incident import Incident
from src.schemas.timeline import IncidentReplaySeries, IncidentTimeline
from src.timeline.replay import IncidentReplayProvider
from src.timeline.synthesizer import TimelineSynthesizer


class AeroService:
    """Core AERO orchestrator mediating business workflows."""

    @classmethod
    def get_health(cls) -> HealthResponse:
        """Returns runtime health status and GCP configuration."""
        return HealthResponse(
            status="HEALTHY",
            version="1.0.0",
            environment=config.environment,
            gcp_project_id=config.project_id,
            gcp_region=config.region,
        )

    @classmethod
    def get_config(cls) -> ConfigResponse:
        """Returns active model and provider configuration."""
        return ConfigResponse(
            project_id=config.project_id,
            region=config.region,
            environment=config.environment,
            reasoning_model=config.reasoning_model,
            fast_model=config.fast_model,
            embedding_model=config.embedding_model,
            diagnostic_provider=config.diagnostic_provider,
        )

    @classmethod
    def list_scenarios(cls, seed: int = 42) -> list[ScenarioSummaryResponse]:
        """Lists available synthetic benchmark scenarios."""
        summaries: list[ScenarioSummaryResponse] = []
        for key, gen_fn in BENCHMARK_SCENARIOS.items():
            bundle = gen_fn(seed=seed)
            gt = bundle.ground_truth
            summaries.append(
                ScenarioSummaryResponse(
                    scenario_id=key,
                    scenario_name=gt.scenario_name,
                    category=gt.category,
                    affected_service=gt.affected_service,
                    trigger_event=gt.trigger_event,
                )
            )
        return summaries

    @classmethod
    def get_scenario_bundle(cls, scenario_key: str, seed: int = 42) -> BenchmarkScenarioBundle:
        """Loads a specific scenario bundle by key."""
        if scenario_key not in BENCHMARK_SCENARIOS:
            raise KeyError(f"Scenario '{scenario_key}' not found. Available: {list(BENCHMARK_SCENARIOS.keys())}")
        gen_fn = BENCHMARK_SCENARIOS[scenario_key]
        return gen_fn(seed=seed)

    @classmethod
    def diagnose(
        cls,
        incident: Incident,
        provider: str | None = None,
    ) -> DiagnoseResponse:
        """Executes AI diagnosis on incident telemetry and performs grounding verification."""
        engine = get_diagnostic_engine(provider=provider)
        start_time = time.perf_counter()
        report = engine.diagnose(incident)
        duration_sec = round(time.perf_counter() - start_time, 3)

        grounding = GroundingVerifier.verify(report, incident)
        return DiagnoseResponse(
            report=report,
            grounding=grounding,
            duration_sec=duration_sec,
        )

    @classmethod
    def synthesize_timeline(
        cls,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None = None,
    ) -> IncidentTimeline:
        """Synthesizes chronological milestone timeline."""
        return TimelineSynthesizer.synthesize(incident, diagnostic_report)

    @classmethod
    def generate_replay(
        cls,
        incident: Incident,
        interval_seconds: int = 60,
    ) -> IncidentReplaySeries:
        """Generates step-by-step replay snapshots."""
        return IncidentReplayProvider.generate_replay_series(incident, interval_seconds=interval_seconds)

    @classmethod
    def generate_postmortem(
        cls,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None = None,
        provider: str | None = None,
    ) -> PostmortemResponse:
        """Authors a Google SRE postmortem and exports markdown."""
        # Ensure diagnostic report and timeline exist
        if diagnostic_report is None:
            diag_resp = cls.diagnose(incident, provider=provider)
            diagnostic_report = diag_resp.report

        timeline = cls.synthesize_timeline(incident, diagnostic_report)
        engine = get_postmortem_engine(provider=provider)
        pm = engine.generate_postmortem(incident, diagnostic_report, timeline)
        md = PostmortemExporter.to_markdown(pm)

        return PostmortemResponse(
            postmortem=pm,
            markdown=md,
        )

    @classmethod
    def evaluate_benchmark(
        cls,
        scenario_keys: list[str] | None = None,
        provider: str | None = "mock",
        seed: int = 42,
    ) -> BenchmarkEvaluationReport:
        """Executes quantitative evaluation suite across benchmark scenarios."""
        keys = scenario_keys or list(BENCHMARK_SCENARIOS.keys())
        bundles = [cls.get_scenario_bundle(k, seed=seed) for k in keys if k in BENCHMARK_SCENARIOS]
        engine = get_diagnostic_engine(provider=provider)
        return IncidentEvaluator.evaluate_benchmark_suite(bundles, engine)

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
from src.chat.engine import VertexAiCopilotEngine, get_copilot_engine
from src.chat.grounding import CopilotGroundingVerifier
from src.config import config
from src.engine.diagnostic_engine import VertexAiDiagnosticEngine, get_diagnostic_engine
from src.engine.grounding_verifier import GroundingVerifier
from src.evaluation.evaluator import BenchmarkEvaluationReport, IncidentEvaluator
from src.postmortem.engine import VertexAiPostmortemEngine, get_postmortem_engine
from src.postmortem.exporter import PostmortemExporter
from src.risk.engine import DeterministicRiskEngine
from src.schemas.chat import ChatResponse
from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.ground_truth import BenchmarkScenarioBundle
from src.schemas.incident import Incident
from src.schemas.risk import RiskAnalysisRequest, RiskAnalysisResponse
from src.schemas.timeline import IncidentReplaySeries, IncidentTimeline
from src.schemas.topology import (
    BlastRadiusReport,
    ChaosExperimentRequest,
    ChaosSimulationResult,
    TopologyGraph,
)
from src.timeline.replay import IncidentReplayProvider
from src.timeline.synthesizer import TimelineSynthesizer
from src.topology.chaos import ChaosSandboxEngine
from src.topology.engine import BlastRadiusEngine
from src.topology.graph import build_canonical_topology_graph


class AeroService:
    """Core business logic service executing operations across AI and benchmark models."""

    @classmethod
    def get_health(cls) -> HealthResponse:
        """Returns service health status and environment details."""
        return HealthResponse(
            status="HEALTHY",
            version="1.0.0",
            environment=config.environment,
            gcp_project_id=config.project_id,
            gcp_region=config.region,
        )

    @classmethod
    def get_config(cls) -> ConfigResponse:
        """Returns public environment configuration metadata."""
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
        provider_name = "live" if isinstance(engine, VertexAiDiagnosticEngine) else "mock"
        return DiagnoseResponse(
            report=report,
            grounding=grounding,
            duration_sec=duration_sec,
            provider=provider_name,
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
        provider_name = "live" if isinstance(engine, VertexAiPostmortemEngine) else "mock"

        return PostmortemResponse(
            postmortem=pm,
            markdown=md,
            provider=provider_name,
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

    @classmethod
    def chat(
        cls,
        scenario_key: str,
        message: str,
        provider: str | None = None,
        seed: int = 42,
    ) -> ChatResponse:
        """Processes an interactive chat question grounded in active scenario telemetry."""
        bundle = cls.get_scenario_bundle(scenario_key, seed=seed)
        incident = bundle.incident

        # Get diagnostic report and timeline for full context
        diag_resp = cls.diagnose(incident, provider=provider)
        diagnostic_report = diag_resp.report
        timeline = cls.synthesize_timeline(incident, diagnostic_report)

        engine = get_copilot_engine(provider=provider)
        response = engine.ask(incident, diagnostic_report, timeline, message, scenario_key)
        response.provider = "live" if isinstance(engine, VertexAiCopilotEngine) else "mock"

        # Grounding validation
        is_grounded, failed_claims = CopilotGroundingVerifier.verify(response, incident)
        response.grounded = is_grounded
        response.failed_claims = failed_claims

        return response

    @classmethod
    def analyze_risk(
        cls,
        request: RiskAnalysisRequest,
        seed: int = 42,
    ) -> RiskAnalysisResponse:
        """Evaluates proposed deployment/configuration changes using deterministic safety rules."""
        incident = None
        if request.scenario_key:
            bundle = cls.get_scenario_bundle(request.scenario_key, seed=seed)
            incident = bundle.incident

        engine = DeterministicRiskEngine()
        return engine.analyze_request(request, incident=incident)

    @classmethod
    def get_topology(
        cls,
        scenario_key: str | None = None,
    ) -> TopologyGraph:
        """Constructs canonical topology with observed incident telemetry mapping."""
        return build_canonical_topology_graph(scenario_key=scenario_key)

    @classmethod
    def get_blast_radius(
        cls,
        service_id: str,
        scenario_key: str | None = None,
    ) -> BlastRadiusReport:
        """Evaluates dynamic blast radius for a given service node."""
        graph = build_canonical_topology_graph(scenario_key=scenario_key)
        engine = BlastRadiusEngine(graph=graph)
        return engine.compute_blast_radius(target_service=service_id)

    @classmethod
    def simulate_chaos(
        cls,
        request: ChaosExperimentRequest,
    ) -> ChaosSimulationResult:
        """Executes a pure, deterministic chaos simulation without mutating persistent state."""
        engine = ChaosSandboxEngine()
        return engine.simulate_chaos(request)

    @classmethod
    def reset_chaos(
        cls,
        scenario_key: str | None = None,
    ) -> TopologyGraph:
        """Resets the topology view back to baseline observed incident state."""
        return build_canonical_topology_graph(scenario_key=scenario_key)

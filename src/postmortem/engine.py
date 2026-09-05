"""Postmortem generation engines supporting Vertex AI Gemini and deterministic mock providers."""

from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config
from src.postmortem.prompts import (
    POSTMORTEM_SYSTEM_INSTRUCTION,
    build_postmortem_prompt,
)
from src.schemas.diagnostic import AeroDiagnosticReport
from src.schemas.incident import Incident
from src.schemas.postmortem import (
    ActionItem,
    ActionItemCategory,
    ActionItemPriority,
    AeroPostmortem,
    FiveWhysAnalysis,
    ImpactSummary,
    RootCauseSummary,
)
from src.schemas.timeline import IncidentTimeline

logger = logging.getLogger("aero.postmortem")


class BasePostmortemEngine(abc.ABC):
    """Abstract base class for postmortem generation engines."""

    @abc.abstractmethod
    def generate_postmortem(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport,
        timeline: IncidentTimeline,
    ) -> AeroPostmortem:
        """Generates a structured AeroPostmortem from incident context, diagnosis, and timeline."""
        raise NotImplementedError


class MockPostmortemEngine(BasePostmortemEngine):
    """Deterministic postmortem provider for offline testing, CI, and evaluation."""

    def generate_postmortem(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport,
        timeline: IncidentTimeline,
    ) -> AeroPostmortem:
        meta = incident.metadata
        svc = meta.affected_service
        now = datetime.now(timezone.utc)
        post_id = f"PM-{meta.incident_id}"

        # 1. Pattern: Memory Leak / OOMKill
        if any("outofmemoryerror" in log.message.lower() or "137" in log.message for log in incident.telemetry.logs):
            return AeroPostmortem(
                postmortem_id=post_id,
                incident_id=meta.incident_id,
                title=f"Postmortem: Worker Service Container Memory Exhaustion & OOMKill ({meta.incident_id})",
                service_name=svc,
                severity=meta.severity.value,
                status="PUBLISHED",
                created_at=now,
                executive_summary=(
                    "On August 30, 2026, the worker-service experienced a severe outage lasting 25 minutes "
                    "due to JVM Java heap exhaustion and subsequent kernel OOMKill (ExitCode 137). The incident was triggered "
                    "when a background batch ingestion job processed an uncompressed 850MB payload that bypassed stream chunking, "
                    "causing 100% memory saturation and HTTP 502 gateway errors on downstream consumers."
                ),
                impact=ImpactSummary(
                    affected_service=svc,
                    severity=meta.severity.value,
                    total_downtime_minutes=timeline.total_duration_minutes,
                    failed_requests_estimate="~4,200 asynchronous batch tasks delayed; 1,150 HTTP 502 responses",
                    impacted_customers_or_flows="Enterprise async batch ingestion pipelines and background report generation",
                ),
                root_cause=RootCauseSummary(
                    title="Unbounded In-Memory Batch Buffer Allocation",
                    category="RESOURCE_EXHAUSTION_MEMORY",
                    trigger_event="850MB uncompressed batch payload ingest at 14:05 UTC",
                    causal_chain=(
                        "Batch worker received oversized payload -> Default Jackson deserializer loaded entire JSON into RAM -> "
                        "Heap crossed 2Gi container limit -> JVM GC paused for 12s -> Linux kernel OOM Killer terminated container with ExitCode 137."
                    ),
                ),
                five_whys=[
                    FiveWhysAnalysis(level=1, why="Why did worker-service stop processing batch jobs?", because="Container process was terminated by Linux kernel OOM killer (ExitCode 137)."),
                    FiveWhysAnalysis(level=2, why="Why was the container OOM-killed?", because="JVM heap utilization climbed continuously to 100% (2.0GiB limit) during payload ingestion."),
                    FiveWhysAnalysis(level=3, why="Why did memory utilization reach 100%?", because="An 850MB uncompressed batch payload was buffered entirely in-memory as a single contiguous object."),
                    FiveWhysAnalysis(level=4, why="Why was the payload buffered entirely in-memory?", because="The batch parser lacked streaming chunk-based ingestion controls for payloads exceeding 100MB."),
                    FiveWhysAnalysis(level=5, why="Why did the parser lack streaming limits?", because="Ingress payload size validation and streaming parser requirements were not enforced in the API gateway schema."),
                ],
                timeline_milestones=timeline.milestones,
                remediation_performed=diagnostic_report.recommended_remediation,
                action_items=[
                    ActionItem(
                        id="ACT-OOM-001",
                        title="Implement Streaming Chunked Ingestion Parser",
                        description="Refactor batch ingestion pipeline to use streaming Jackson parser with max 50MB in-memory buffer.",
                        category=ActionItemCategory.MITIGATION,
                        priority=ActionItemPriority.P0,
                        owner="Data Ingest Platform Team",
                        estimated_effort="2 days",
                        verification="Load test with 2GB batch file succeeds with heap stable under 512MB.",
                    ),
                    ActionItem(
                        id="ACT-OOM-002",
                        title="Increase Cloud Run Container Memory Limit to 4Gi",
                        description="Update Cloud Run service manifest memory allocation from 2Gi to 4Gi with vertical autoscaling.",
                        category=ActionItemCategory.RESILIENCE,
                        priority=ActionItemPriority.P1,
                        owner="Cloud Infrastructure Team",
                        estimated_effort="1 day",
                        verification="gcloud run services describe verifies 4Gi memory limit.",
                    ),
                    ActionItem(
                        id="ACT-OOM-003",
                        title="Enforce Maximum Payload Size Guardrail on API Gateway",
                        description="Configure Cloud Armor and Gateway request size limit at 100MB with 413 Payload Too Large responses.",
                        category=ActionItemCategory.PROCESS,
                        priority=ActionItemPriority.P1,
                        owner="API Gateway Team",
                        estimated_effort="1 day",
                        verification="Requests exceeding 100MB rejected with HTTP 413.",
                    ),
                ],
                lessons_learned_what_went_well=[
                    "Automated Cloud Monitoring alerts paged on-call SRE within 3 minutes of memory saturation.",
                    "AERO diagnostic engine correctly isolated JVM OutOfMemoryError and ExitCode 137 within seconds.",
                ],
                lessons_learned_what_went_wrong=[
                    "Batch workers lacked payload pre-validation, allowing an 850MB request to reach execution.",
                    "Container memory limits were too tight (2Gi) for concurrent batch worker thread pools.",
                ],
                lessons_learned_where_we_got_lucky=[
                    "Downstream queues buffered incoming tasks without permanent message loss during pod reboot cycles.",
                ],
            )

        # 2. Pattern: DB Connection Pool Exhaustion
        elif any("hikaripool" in log.message.lower() or "connectiontimeout" in log.message.lower() for log in incident.telemetry.logs):
            return AeroPostmortem(
                postmortem_id=post_id,
                incident_id=meta.incident_id,
                title=f"Postmortem: Order Service Database Connection Pool Starvation ({meta.incident_id})",
                service_name=svc,
                severity=meta.severity.value,
                status="PUBLISHED",
                created_at=now,
                executive_summary=(
                    "On August 30, 2026, order-service experienced a severe SEV1 outage where checkout requests "
                    "suffered 96% HTTP 504 Gateway Timeouts. The incident was initiated by deployment of release v2.4.1, "
                    "which introduced an unindexed sequential scan query on the orders table, exhausting the HikariCP "
                    "connection pool (20/20 active connections) and locking all worker threads."
                ),
                impact=ImpactSummary(
                    affected_service=svc,
                    severity=meta.severity.value,
                    total_downtime_minutes=timeline.total_duration_minutes,
                    failed_requests_estimate="~12,800 checkout requests timed out (504)",
                    impacted_customers_or_flows="All customer checkout workflows across web and mobile storefronts",
                ),
                root_cause=RootCauseSummary(
                    title="Unindexed Database Query & HikariCP Pool Saturation",
                    category="DATABASE_CONNECTION_EXHAUSTION",
                    trigger_event="Deployment of order-service:v2.4.1 at 14:03 UTC",
                    causal_chain=(
                        "Release v2.4.1 deployed -> Unindexed customer order history query performed full table scan (15s latency) -> "
                        "Active connection count reached pool maximum (20/20) -> HikariCP acquisition timeout exceeded (30,000ms) -> "
                        "All checkout threads blocked resulting in cascading HTTP 504 timeouts."
                    ),
                ),
                five_whys=[
                    FiveWhysAnalysis(level=1, why="Why did checkout requests fail with HTTP 504?", because="Order service threads timed out waiting for database connection pool access."),
                    FiveWhysAnalysis(level=2, why="Why were database connections unavailable?", because="All 20 connections in the HikariCP pool were continuously saturated by slow-running transactions."),
                    FiveWhysAnalysis(level=3, why="Why were transactions running slowly?", because="A new query in release v2.4.1 executed a full table scan taking 15+ seconds per checkout."),
                    FiveWhysAnalysis(level=4, why="Why did the query perform a full table scan?", because="The orders table lacked a composite index on (customer_id, status)."),
                    FiveWhysAnalysis(level=5, why="Why was an unindexed query released to production?", because="Pre-deployment query performance regression tests were not enforced in the CI/CD pipeline."),
                ],
                timeline_milestones=timeline.milestones,
                remediation_performed=diagnostic_report.recommended_remediation,
                action_items=[
                    ActionItem(
                        id="ACT-DB-001",
                        title="Rollback order-service to Stable Release v2.4.0",
                        description="Perform zero-downtime rollback to v2.4.0 container image to eliminate slow query.",
                        category=ActionItemCategory.MITIGATION,
                        priority=ActionItemPriority.P0,
                        owner="Order Team On-Call",
                        estimated_effort="30 minutes",
                        verification="database/pool/active_connections drops below 10 and 504 errors resolve.",
                    ),
                    ActionItem(
                        id="ACT-DB-002",
                        title="Add Composite Database Index on orders(customer_id, status)",
                        description="Apply schema migration concurrently in PostgreSQL to index checkout search queries.",
                        category=ActionItemCategory.RESILIENCE,
                        priority=ActionItemPriority.P1,
                        owner="Database Engineering Team",
                        estimated_effort="1 day",
                        verification="EXPLAIN ANALYZE confirms Index Scan with latency < 5ms.",
                    ),
                    ActionItem(
                        id="ACT-DB-003",
                        title="Implement Automated Query Linter & Migration Safety Gates in CI",
                        description="Enforce pg_stat_statements query plan analysis during staging integration testing.",
                        category=ActionItemCategory.TESTING,
                        priority=ActionItemPriority.P1,
                        owner="Platform CI/CD Team",
                        estimated_effort="1 sprint",
                        verification="CI fails on queries exceeding 100ms execution plan estimate.",
                    ),
                ],
                lessons_learned_what_went_well=[
                    "Rollback procedure was well-documented in the database runbook and stabilized connections immediately.",
                    "AERO correlated the v2.4.1 deployment timestamp with HikariCP saturation in under 5 seconds.",
                ],
                lessons_learned_what_went_wrong=[
                    "Connection pool maximum (20) was undersized for peak transaction concurrency.",
                    "Pre-deployment staging database had inadequate synthetic data volume to surface sequential scan latency.",
                ],
                lessons_learned_where_we_got_lucky=[
                    "Database server CPU did not crash, avoiding database replica failover delays.",
                ],
            )

        # Generic Fallback
        return AeroPostmortem(
            postmortem_id=post_id,
            incident_id=meta.incident_id,
            title=f"Postmortem: Service Incident on {svc} ({meta.incident_id})",
            service_name=svc,
            severity=meta.severity.value,
            status="PUBLISHED",
            created_at=now,
            executive_summary=f"Incident {meta.incident_id} affected {svc} with elevated error rates and health degradation.",
            impact=ImpactSummary(
                affected_service=svc,
                severity=meta.severity.value,
                total_downtime_minutes=timeline.total_duration_minutes,
                impacted_customers_or_flows="General service requests",
            ),
            root_cause=RootCauseSummary(
                title=diagnostic_report.probable_root_cause.title,
                category=diagnostic_report.probable_root_cause.category,
                trigger_event=diagnostic_report.probable_root_cause.trigger_event or "Service Anomaly",
                causal_chain=diagnostic_report.probable_root_cause.description,
            ),
            five_whys=[
                FiveWhysAnalysis(level=1, why=f"Why was {svc} degraded?", because="Service telemetry indicated abnormal error rates."),
                FiveWhysAnalysis(level=2, why="Why were error rates elevated?", because="Underlying component experienced operational anomaly."),
                FiveWhysAnalysis(level=3, why="Why did the anomaly manifest?", because="Trigger event exceeded steady-state tolerance."),
                FiveWhysAnalysis(level=4, why="Why was tolerance exceeded?", because="System lacked automated defensive circuit breaking."),
                FiveWhysAnalysis(level=5, why="Why was circuit breaking absent?", because="Architecture design prioritized throughput over degraded fallback."),
            ],
            timeline_milestones=timeline.milestones,
            remediation_performed=diagnostic_report.recommended_remediation,
            action_items=[
                ActionItem(
                    id=f"ACT-{svc[:3].upper()}-001",
                    title="Implement Resilient Circuit Breaker & Health Check",
                    description="Add automated degradation fallback logic.",
                    category=ActionItemCategory.RESILIENCE,
                    priority=ActionItemPriority.P1,
                    owner="Service Team",
                    estimated_effort="1 sprint",
                    verification="Health status recovers automatically under fault injection.",
                )
            ],
            lessons_learned_what_went_well=["Incident was mitigated within target MTTR."],
            lessons_learned_what_went_wrong=["Initial triage required manual investigation."],
            lessons_learned_where_we_got_lucky=["No customer data was corrupted."],
        )


class VertexAiPostmortemEngine(BasePostmortemEngine):
    """Live Google Cloud Vertex AI Gemini postmortem authoring engine."""

    def __init__(
        self,
        project_id: str | None = None,
        region: str | None = None,
        model_name: str | None = None,
    ):
        self.project_id = project_id or config.project_id
        self.region = region or config.region
        self.model_name = model_name or config.reasoning_model
        self._client = None

    def _ensure_init(self) -> None:
        if self._client is None:
            from google import genai
            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.region,
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_postmortem(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport,
        timeline: IncidentTimeline,
    ) -> AeroPostmortem:
        self._ensure_init()
        assert self._client is not None
        from google.genai import types

        prompt = build_postmortem_prompt(incident, diagnostic_report, timeline)

        logger.info(f"Invoking Vertex AI Gemini ({self.model_name}) for postmortem authoring on {incident.metadata.incident_id}")
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=POSTMORTEM_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=AeroPostmortem,
                temperature=0.1,
            ),
        )

        report_text = response.text or ""
        if report_text.startswith("```json"):
            report_text = report_text.removeprefix("```json").removesuffix("```").strip()
        elif report_text.startswith("```"):
            report_text = report_text.removeprefix("```").removesuffix("```").strip()

        return AeroPostmortem.model_validate_json(report_text)


def get_postmortem_engine(provider: str | None = None) -> BasePostmortemEngine:
    """Factory creating the appropriate postmortem engine instance."""
    mode = provider or config.diagnostic_provider
    if mode == "vertex":
        return VertexAiPostmortemEngine()
    elif mode == "mock":
        return MockPostmortemEngine()
    elif mode == "auto":
        import os
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                return VertexAiPostmortemEngine()
            except Exception:
                return MockPostmortemEngine()
        return MockPostmortemEngine()
    else:
        return MockPostmortemEngine()

"""AI Diagnostic Reasoning Engine supporting Vertex AI Gemini and deterministic mock providers."""

from __future__ import annotations

import abc
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config
from src.engine.correlator import TelemetryCorrelator
from src.engine.prompts import SYSTEM_INSTRUCTION, build_diagnostic_prompt
from src.schemas.diagnostic import (
    AeroDiagnosticReport,
    ConfidenceLevel,
    ConfidenceRating,
    ProbableRootCause,
    RecommendedRemediation,
    SignalType,
    SupportingEvidence,
)
from src.schemas.incident import Incident

logger = logging.getLogger("aero.engine")


class BaseDiagnosticEngine(abc.ABC):
    """Abstract base class for AERO AI Diagnostic engines."""

    @abc.abstractmethod
    def diagnose(self, incident: Incident) -> AeroDiagnosticReport:
        """Analyzes an incident's telemetry and returns a structured AeroDiagnosticReport."""
        raise NotImplementedError


class MockDiagnosticEngine(BaseDiagnosticEngine):
    """Deterministic diagnostic provider for offline testing, CI, and evaluation."""

    def diagnose(self, incident: Incident) -> AeroDiagnosticReport:
        meta = incident.metadata
        svc = meta.affected_service

        # 1. Pattern: Memory Leak / OOMKill
        if any("outofmemoryerror" in log.message.lower() or "137" in log.message for log in incident.telemetry.logs):
            oom_log = next(
                (l for l in incident.telemetry.logs if "137" in l.message),
                incident.telemetry.logs[0],
            )
            oom_heap_log = next(
                (l for l in incident.telemetry.logs if "outofmemoryerror" in l.message.lower()),
                oom_log,
            )
            return AeroDiagnosticReport(
                incident_id=meta.incident_id,
                service_name=svc,
                severity=meta.severity.value,
                incident_summary="Worker service experienced uncompressed batch ingest overload causing Java heap exhaustion and kernel OOMKill (ExitCode 137).",
                probable_root_cause=ProbableRootCause(
                    title="Container Memory Exhaustion & OOMKill",
                    description="Unbounded memory accumulation during 850MB batch payload ingestion triggered OutOfMemoryError and kernel termination with ExitCode 137.",
                    category="RESOURCE_EXHAUSTION_MEMORY",
                    trigger_event="Batch ingest job received uncompressed 850MB payload at 14:05 UTC.",
                ),
                confidence_level=ConfidenceLevel(
                    score=0.96,
                    rating=ConfidenceRating.HIGH,
                    rationale="Direct convergence of container/memory_utilization saturation, JVM OutOfMemoryError, and ExitCode 137 termination log.",
                ),
                supporting_evidence=[
                    SupportingEvidence(
                        signal_type=SignalType.METRIC,
                        timestamp=incident.telemetry.time_window_start,
                        source="container/memory_utilization",
                        content="Memory utilization climbed to 100% capacity.",
                        relevance="Confirms progressive heap exhaustion.",
                    ),
                    SupportingEvidence(
                        signal_type=SignalType.LOG,
                        timestamp=oom_heap_log.timestamp,
                        source=svc,
                        content=oom_heap_log.message,
                        relevance="Java heap space OutOfMemoryError stack trace.",
                    ),
                    SupportingEvidence(
                        signal_type=SignalType.LOG,
                        timestamp=oom_log.timestamp,
                        source=svc,
                        content=oom_log.message,
                        relevance="Explicit kernel container kill citing ExitCode 137 (OOMKilled).",
                    ),
                ],
                recommended_remediation=RecommendedRemediation(
                    immediate_steps=[
                        "Restart worker-service deployment pods to clear hung tasks",
                        "Increase container memory limit from 2Gi to 4Gi in manifest",
                        "Enable streaming chunked parser for batch payloads",
                    ],
                    dry_run_command="gcloud run services update worker-service --memory 4Gi --dry-run",
                    verification_metric="container/memory_utilization stabilizes under 60% and HTTP 502 error rate drops to 0%",
                    rollback_plan="Revert container memory settings if worker startup fails.",
                ),
            )

        # 2. Pattern: DB Connection Pool Exhaustion
        elif any("hikaripool" in log.message.lower() or "connectiontimeout" in log.message.lower() for log in incident.telemetry.logs):
            h_log = next(
                (l for l in incident.telemetry.logs if "hikaripool" in l.message.lower()),
                incident.telemetry.logs[0],
            )
            deploy = incident.telemetry.deployments[0] if incident.telemetry.deployments else None
            evidence = [
                SupportingEvidence(
                    signal_type=SignalType.METRIC,
                    timestamp=incident.telemetry.time_window_start,
                    source="database/pool/active_connections",
                    content="Active DB connections saturated at max capacity (20/20).",
                    relevance="Confirms connection pool starvation.",
                ),
                SupportingEvidence(
                    signal_type=SignalType.LOG,
                    timestamp=h_log.timestamp,
                    source=svc,
                    content=h_log.message,
                    relevance="HikariPool-1 - Connection is not available timeout log.",
                ),
            ]
            if deploy:
                evidence.append(
                    SupportingEvidence(
                        signal_type=SignalType.DEPLOYMENT,
                        timestamp=deploy.timestamp,
                        source=svc,
                        content=f"Deployed version {deploy.version}: {deploy.change_summary}",
                        relevance="Preceded the database connection pool saturation.",
                    )
                )

            return AeroDiagnosticReport(
                incident_id=meta.incident_id,
                service_name=svc,
                severity=meta.severity.value,
                incident_summary="Order service database connection pool exhausted following release v2.4.1 unindexed query deployment, causing 96% HTTP 504 timeouts.",
                probable_root_cause=ProbableRootCause(
                    title="Database Connection Pool Starvation",
                    description="Release v2.4.1 introduced a slow sequential scan query on orders table, exhausting HikariCP connection pool and blocking checkout requests.",
                    category="DATABASE_CONNECTION_EXHAUSTION",
                    trigger_event=f"Deployment of order-service:{deploy.version if deploy else 'v2.4.1'} at 14:03 UTC.",
                ),
                confidence_level=ConfidenceLevel(
                    score=0.95,
                    rating=ConfidenceRating.HIGH,
                    rationale="Direct causal link between v2.4.1 deploy timestamp, active connection metric saturation (20/20), and HikariCP acquisition timeouts.",
                ),
                supporting_evidence=evidence,
                recommended_remediation=RecommendedRemediation(
                    immediate_steps=[
                        "Rollback order-service to previous stable release v2.4.0",
                        "Add index on orders (status, customer_id)",
                        "Temporarily scale connection pool capacity to 40",
                    ],
                    dry_run_command="gcloud run services update order-service --image gcr.io/aero-prod/order-service:v2.4.0 --dry-run",
                    verification_metric="database/pool/active_connections drops below 10 and HTTP 504 error rate drops to 0%",
                    rollback_plan="If rollback fails, restart Cloud SQL replica pool.",
                ),
            )

        # 3. Pattern: Config Drift / JWKS mismatch
        elif any("unknownhostexception" in log.message.lower() or "jwtvalidation" in log.message.lower() for log in incident.telemetry.logs):
            err_log = next(
                (l for l in incident.telemetry.logs if "unknownhostexception" in l.message.lower()),
                incident.telemetry.logs[0],
            )
            jwt_log = next(
                (l for l in incident.telemetry.logs if "jwtvalidation" in l.message.lower()),
                err_log,
            )
            deploy = incident.telemetry.deployments[0] if incident.telemetry.deployments else None
            evidence = [
                SupportingEvidence(
                    signal_type=SignalType.LOG,
                    timestamp=err_log.timestamp,
                    source=svc,
                    content=err_log.message,
                    relevance="DNS failure during JWKS public key resolution (UnknownHostException).",
                ),
                SupportingEvidence(
                    signal_type=SignalType.LOG,
                    timestamp=jwt_log.timestamp,
                    source=svc,
                    content=jwt_log.message,
                    relevance="JWTValidationException indicating public key retrieval failure.",
                ),
                SupportingEvidence(
                    signal_type=SignalType.METRIC,
                    timestamp=incident.telemetry.time_window_start,
                    source="auth/jwt_verification_failure_rate",
                    content="JWT verification failure rate spiked to 99%.",
                    relevance="Direct evidence of token authentication collapse.",
                ),
            ]
            if deploy:
                evidence.append(
                    SupportingEvidence(
                        signal_type=SignalType.DEPLOYMENT,
                        timestamp=deploy.timestamp,
                        source=svc,
                        content=f"Config update {deploy.version}: {deploy.change_summary}",
                        relevance="Triggered invalid JWKS endpoint change.",
                    )
                )

            return AeroDiagnosticReport(
                incident_id=meta.incident_id,
                service_name=svc,
                severity=meta.severity.value,
                incident_summary="Auth service experiencing global 401 Unauthorized authentication collapse due to unresolvable JWKS endpoint in ConfigMap rev-42.",
                probable_root_cause=ProbableRootCause(
                    title="Configuration Drift & Unresolvable JWKS Host",
                    description="ConfigMap revision rev-42 configured an invalid internal hostname (auth-internal.prod.local), causing DNS UnknownHostException and token signature validation failures.",
                    category="CONFIGURATION_DRIFT",
                    trigger_event="ConfigMap update (config-rev-42) at 14:02 UTC.",
                ),
                confidence_level=ConfidenceLevel(
                    score=0.98,
                    rating=ConfidenceRating.HIGH,
                    rationale="Direct correlation between ConfigMap reload log, UnknownHostException DNS error, and 99% JWT failure spike.",
                ),
                supporting_evidence=evidence,
                recommended_remediation=RecommendedRemediation(
                    immediate_steps=[
                        "Rollback auth-service ConfigMap to previous revision rev-41",
                        "Correct JWKS endpoint URL to https://auth.internal.production/keys",
                        "Trigger config reload on auth-service pods",
                    ],
                    dry_run_command="kubectl rollout undo deployment/auth-service --dry-run=server",
                    verification_metric="auth/jwt_verification_failure_rate drops to 0% and HTTP 401 errors resolve",
                    rollback_plan="Re-apply revision rev-41 if rollback encounters validation errors.",
                ),
            )

        # 4. Pattern: Dependency Latency / Thread Starvation
        elif any("worker pool starvation" in log.message.lower() or "partner-payments" in log.message.lower() for log in incident.telemetry.logs):
            err_log = next(
                (l for l in incident.telemetry.logs if "worker pool starvation" in l.message.lower()),
                incident.telemetry.logs[0],
            )
            outbound_log = next(
                (l for l in incident.telemetry.logs if "api.partner-payments.io" in l.message.lower()),
                err_log,
            )
            return AeroDiagnosticReport(
                incident_id=meta.incident_id,
                service_name=svc,
                severity=meta.severity.value,
                incident_summary="Checkout service worker thread pool starved due to upstream payment partner latency (>28s) without client-side timeouts.",
                probable_root_cause=ProbableRootCause(
                    title="Downstream Dependency Latency & Thread Pool Starvation",
                    description="Upstream third-party payment partner latency spiked to 28s. Due to missing client socket timeouts, all 100 worker threads blocked waiting on I/O, freezing checkout-service.",
                    category="DEPENDENCY_OUTAGE_TIMEOUT",
                    trigger_event="Upstream partner API (api.partner-payments.io) latency degradation at 14:04 UTC.",
                ),
                confidence_level=ConfidenceLevel(
                    score=0.94,
                    rating=ConfidenceRating.HIGH,
                    rationale="Convergence of partner latency spike (28.5s), worker thread pool saturation (100/100), low CPU utilization (2%), and health check timeouts.",
                ),
                supporting_evidence=[
                    SupportingEvidence(
                        signal_type=SignalType.METRIC,
                        timestamp=incident.telemetry.time_window_start,
                        source="dependency/partner_payment_latency_p99",
                        content="Partner payment latency spiked to 28500ms on api.partner-payments.io.",
                        relevance="Proves upstream partner was the primary latency bottleneck.",
                    ),
                    SupportingEvidence(
                        signal_type=SignalType.METRIC,
                        timestamp=incident.telemetry.time_window_start,
                        source="server/active_worker_threads",
                        content="Active worker threads reached 100% capacity.",
                        relevance="Confirms thread pool starvation.",
                    ),
                    SupportingEvidence(
                        signal_type=SignalType.LOG,
                        timestamp=err_log.timestamp,
                        source=svc,
                        content=err_log.message,
                        relevance="Worker pool starvation in ThreadPoolExecutor.",
                    ),
                    SupportingEvidence(
                        signal_type=SignalType.LOG,
                        timestamp=outbound_log.timestamp,
                        source=svc,
                        content=outbound_log.message,
                        relevance="Outbound call to api.partner-payments.io exceeding threshold.",
                    ),
                ],
                recommended_remediation=RecommendedRemediation(
                    immediate_steps=[
                        "Configure 2500ms socket timeout and circuit breaker on partner-payments client",
                        "Enable async degraded checkout fallback queue",
                        "Restart checkout-service pods to clear hung threads",
                    ],
                    dry_run_command="gcloud run services update checkout-service --set-env-vars PARTNER_TIMEOUT_MS=2500 --dry-run",
                    verification_metric="server/active_worker_threads drops below 30 and P99 latency returns under 200ms",
                    rollback_plan="Revert timeout config if partner API stabilizes.",
                ),
            )

        # 5. Pattern: Cache Stampede / Deserialization
        elif any("serializationerror" in log.message.lower() or "cache stampede" in log.message.lower() for log in incident.telemetry.logs):
            ser_log = next(
                (l for l in incident.telemetry.logs if "serializationerror" in l.message.lower()),
                incident.telemetry.logs[0],
            )
            deploy = incident.telemetry.deployments[0] if incident.telemetry.deployments else None
            evidence = [
                SupportingEvidence(
                    signal_type=SignalType.LOG,
                    timestamp=ser_log.timestamp,
                    source=svc,
                    content=ser_log.message,
                    relevance="SerializationError on Redis cache key prefix.",
                ),
                SupportingEvidence(
                    signal_type=SignalType.METRIC,
                    timestamp=incident.telemetry.time_window_start,
                    source="redis/cache_hit_ratio",
                    content="Cache hit ratio collapsed from 98.5% to 1.8%.",
                    relevance="Proves total cache bypass.",
                ),
                SupportingEvidence(
                    signal_type=SignalType.METRIC,
                    timestamp=incident.telemetry.time_window_start,
                    source="database/cpu_utilization",
                    content="Database CPU reached 100% under cache stampede.",
                    relevance="Confirms database overload.",
                ),
            ]
            if deploy:
                evidence.append(
                    SupportingEvidence(
                        signal_type=SignalType.DEPLOYMENT,
                        timestamp=deploy.timestamp,
                        source=svc,
                        content=f"Deployed version {deploy.version}: {deploy.change_summary}",
                        relevance="Introduced incompatible binary cache codec.",
                    )
                )

            return AeroDiagnosticReport(
                incident_id=meta.incident_id,
                service_name=svc,
                severity=meta.severity.value,
                incident_summary="Catalog service cache stampede saturated PostgreSQL CPU at 100% following v3.1.0 incompatible binary serializer deployment.",
                probable_root_cause=ProbableRootCause(
                    title="Cache Key Deserialization Failure & Database Stampede",
                    description="Release v3.1.0 introduced an incompatible SnappyBinaryCodec serializer, causing 98% Redis cache misses and a massive unmitigated cache stampede onto PostgreSQL.",
                    category="CACHE_STAMPEDE_SERIALIZATION",
                    trigger_event=f"Deployment of catalog-service:{deploy.version if deploy else 'v3.1.0'} at 14:02 UTC.",
                ),
                confidence_level=ConfidenceLevel(
                    score=0.97,
                    rating=ConfidenceRating.HIGH,
                    rationale="Direct causal sequence from v3.1.0 deployment -> Redis SerializationError -> cache hit ratio collapse (1.8%) -> Database 100% CPU saturation.",
                ),
                supporting_evidence=evidence,
                recommended_remediation=RecommendedRemediation(
                    immediate_steps=[
                        "Rollback catalog-service to previous release v3.0.9",
                        "Flush corrupted Redis keys with prefix 'catalog:v2'",
                        "Implement mutex/singleflight locking on cache miss",
                    ],
                    dry_run_command="gcloud run services update catalog-service --image gcr.io/aero-prod/catalog-service:v3.0.9 --dry-run",
                    verification_metric="redis/cache_hit_ratio recovers above 95% and database/cpu_utilization drops below 30%",
                    rollback_plan="Re-enable previous cache instance if key flush causes transient latency.",
                ),
            )

        # Generic Fallback
        return AeroDiagnosticReport(
            incident_id=meta.incident_id,
            service_name=svc,
            severity=meta.severity.value,
            incident_summary=f"Incident detected on {svc}.",
            probable_root_cause=ProbableRootCause(
                title="Service Anomaly",
                description="Elevated error rates detected across service telemetry.",
                category="GENERIC_ANOMALY",
            ),
            confidence_level=ConfidenceLevel(
                score=0.70,
                rating=ConfidenceRating.MEDIUM,
                rationale="Telemetry shows anomalous error logs and degraded health status.",
            ),
            supporting_evidence=[],
            recommended_remediation=RecommendedRemediation(
                immediate_steps=["Inspect service logs and restart deployment"],
                verification_metric="Health status returns to HEALTHY",
                rollback_plan="Revert recent deployments",
            ),
        )


class VertexAiDiagnosticEngine(BaseDiagnosticEngine):
    """Live Google Cloud Vertex AI Gemini diagnostic reasoning engine."""

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
    def diagnose(self, incident: Incident) -> AeroDiagnosticReport:
        self._ensure_init()
        assert self._client is not None
        from google.genai import types

        summary = TelemetryCorrelator.correlate(incident)
        prompt = build_diagnostic_prompt(incident, summary)

        logger.info(f"Invoking Vertex AI Gemini ({self.model_name}) for incident {incident.metadata.incident_id}")
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=AeroDiagnosticReport,
                temperature=0.1,
            ),
        )

        report_text = response.text or ""
        if report_text.startswith("```json"):
            report_text = report_text.removeprefix("```json").removesuffix("```").strip()
        elif report_text.startswith("```"):
            report_text = report_text.removeprefix("```").removesuffix("```").strip()

        return AeroDiagnosticReport.model_validate_json(report_text)


def get_diagnostic_engine(provider: str | None = None) -> BaseDiagnosticEngine:
    """Factory creating the appropriate diagnostic engine instance."""
    mode = provider or config.diagnostic_provider
    if mode == "vertex":
        return VertexAiDiagnosticEngine()
    elif mode == "mock":
        return MockDiagnosticEngine()
    elif mode == "auto":
        import os
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                engine = VertexAiDiagnosticEngine()
                return engine
            except Exception:
                return MockDiagnosticEngine()
        return MockDiagnosticEngine()
    else:
        return MockDiagnosticEngine()

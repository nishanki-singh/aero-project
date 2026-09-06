"""Grounded SRE Copilot reasoning engines (Deterministic Mock & Live Vertex AI)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from src.chat.grounding import CopilotGroundingVerifier
from src.chat.prompts import COPILOT_SYSTEM_INSTRUCTION, build_copilot_prompt
from src.config import config
from src.schemas.chat import ChatResponse, EvidenceItem
from src.schemas.diagnostic import AeroDiagnosticReport, SignalType
from src.schemas.incident import Incident
from src.schemas.timeline import IncidentTimeline


class BaseCopilotEngine(ABC):
    """Abstract interface for SRE Copilot reasoning engines."""

    @abstractmethod
    def ask(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None,
        timeline: IncidentTimeline | None,
        question: str,
        scenario_key: str,
    ) -> ChatResponse:
        """Generates an evidence-grounded response to an SRE user query."""


class MockCopilotEngine(BaseCopilotEngine):
    """Deterministic, offline SRE Copilot engine covering all 5 benchmark scenarios."""

    def ask(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None,
        timeline: IncidentTimeline | None,
        question: str,
        scenario_key: str,
    ) -> ChatResponse:
        q = question.strip().lower()
        svc = incident.metadata.affected_service
        telemetry = incident.telemetry

        # 1. Identify scenario category
        is_oom = any("oom" in l.message.lower() or "exitcode 137" in l.message.lower() for l in telemetry.logs)
        is_db = any("hikaripool" in l.message.lower() or "connectiontimeout" in l.message.lower() for l in telemetry.logs)
        is_cfg = any("unknownhostexception" in l.message.lower() or "jwtvalidation" in l.message.lower() for l in telemetry.logs)
        is_dep = any("worker pool starvation" in l.message.lower() or "partner-payments" in l.message.lower() for l in telemetry.logs)
        is_cache = any("serializationerror" in l.message.lower() or "cache stampede" in l.message.lower() for l in telemetry.logs)

        # 2. Match Question Category
        # Category A: Root Cause
        if any(w in q for w in ("cause", "root", "why did", "failing", "broken", "reason")):
            return self._answer_root_cause(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category B: Evidence
        elif any(w in q for w in ("evidence", "strongest", "proof", "telemetry", "logs", "metrics", "support", "signal")):
            return self._answer_evidence(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category C: Timeline & Changes
        elif any(w in q for w in ("change", "deploy", "release", "timeline", "when", "before the incident")):
            return self._answer_changes(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category D: Impact
        elif any(w in q for w in ("impact", "customer", "how long", "downtime", "user", "duration", "blast")):
            return self._answer_impact(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category E: Remediation & Verification
        elif any(w in q for w in ("remediat", "verify", "verification", "rollback", "dry-run", "dry run", "mitigat", "fix", "apply")):
            return self._answer_remediation(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category F: Next Steps / Safest Action
        elif any(w in q for w in ("next", "safest", "check next", "what should i do", "step", "recommend")):
            return self._answer_next_steps(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category G: Missing Evidence
        elif any(w in q for w in ("missing", "gap", "unobserved", "blind spot", "what else")):
            return self._answer_missing_evidence(scenario_key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, telemetry)

        # Category H: Unsupported / Unknown Inquiry
        else:
            return self._answer_unsupported(scenario_key, svc, question)

    # -------------------------------------------------------------------------
    # Scenario-Specific Answer Builders
    # -------------------------------------------------------------------------

    def _answer_root_cause(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        if is_oom:
            return ChatResponse(
                scenario_key=key,
                answer=f"The primary root cause of the **{svc}** outage is **Unbounded In-Memory Batch Buffer Allocation** leading to JVM heap exhaustion and container OOMKill (ExitCode 137).",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="Linux kernel OOM killer terminated container process with ExitCode 137",
                        log_snippet="ExitCode 137 (OOMKilled)",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="JVM OutOfMemoryError: Java heap space during batch payload ingest",
                        log_snippet="OutOfMemoryError: Java heap space",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.METRIC,
                        source="container/memory_utilization",
                        metric_name="container/memory_utilization",
                        description="container/memory_utilization reached 100% capacity limit (2.0GiB)",
                    ),
                ],
                inferences=[
                    "An uncompressed 850MB batch payload was ingested without streaming chunking, exceeding the 2GiB container cgroup memory boundary.",
                    "The JVM GC paused for 12s attempting compaction before the kernel issued a SIGKILL to pod worker-service.",
                ],
                recommendations=[
                    "Verify container memory limits in Cloud Run / Kubernetes manifests before increasing to 4Gi.",
                    "Implement a streaming chunked Jackson parser for all payloads exceeding 100MB.",
                ],
                confidence=0.98,
                grounded=True,
            )
        elif is_db:
            return ChatResponse(
                scenario_key=key,
                answer=f"The primary root cause of the **{svc}** outage is **HikariCP Connection Pool Saturation** triggered by an unindexed query introduced in release `v2.4.1`.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.METRIC,
                        source="database/pool/active_connections",
                        metric_name="database/pool/active_connections",
                        description="database/pool/active_connections remained saturated at 20/20 max connections",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="HikariCP connection acquisition timeout after 30000ms",
                        log_snippet="ConnectionTimeout: HikariPool-1 - Connection is not available",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description="Deployment of order-service version v2.4.1 applied prior to connection exhaustion",
                    ),
                ],
                inferences=[
                    "Release v2.4.1 added an unindexed sequential scan on orders(customer_id, status), taking 15s per query.",
                    "Saturated connection pool starved all checkout worker threads, producing 96% HTTP 504 Gateway Timeouts.",
                ],
                recommendations=[
                    "Rollback order-service container image to stable revision v2.4.0.",
                    "Apply composite index migration on orders(customer_id, status) before re-deploying.",
                ],
                confidence=0.97,
                grounded=True,
            )
        elif is_cfg:
            return ChatResponse(
                scenario_key=key,
                answer=f"The primary root cause of the **{svc}** outage is **Configuration Drift & Unresolvable JWKS Host** applied in ConfigMap `config-rev-42`.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="DNS resolution failure for JWKS endpoint hostname auth-internal.prod.local",
                        log_snippet="UnknownHostException: auth-internal.prod.local",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.METRIC,
                        source="auth/jwt_verification_failure_rate",
                        metric_name="auth/jwt_verification_failure_rate",
                        description="auth/jwt_verification_failure_rate spiked to 99.2%",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description="ConfigMap update to version config-rev-42 reloaded in auth-service",
                    ),
                ],
                inferences=[
                    "ConfigMap config-rev-42 introduced an unresolvable staging hostname into production.",
                    "Inability to fetch public keys caused all JWT validation attempts to fail with HTTP 401 Unauthorized.",
                ],
                recommendations=[
                    "Rollback ConfigMap to revision config-rev-41 and reload pods.",
                    "Add automated hostname resolution validation gates to ConfigMap CI pipeline.",
                ],
                confidence=0.99,
                grounded=True,
            )
        elif is_dep:
            return ChatResponse(
                scenario_key=key,
                answer=f"The primary root cause of the **{svc}** outage is **Downstream Dependency Latency & Worker Thread Starvation** caused by partner payments API timeouts.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="Worker pool starvation: ThreadPoolExecutor queue full (active=100, queue_size=500)",
                        log_snippet="Worker pool starvation: ThreadPoolExecutor queue full",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.METRIC,
                        source="dependency/partner_payment_latency_p99",
                        metric_name="dependency/partner_payment_latency_p99",
                        description="dependency/partner_payment_latency_p99 degraded to 28.5s",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description="Zero deployments recorded in observation window",
                    ),
                ],
                inferences=[
                    "Outbound HTTP client lacked socket timeouts and circuit breaking for api.partner-payments.io.",
                    "All synchronous payment worker threads locked waiting for socket I/O, causing incoming checkout requests to queue indefinitely.",
                ],
                recommendations=[
                    "Configure client-side socket read timeout (5000ms) on third-party payment client.",
                    "Implement circuit breaker and fallback queue for partner API degradation.",
                ],
                confidence=0.96,
                grounded=True,
            )
        else:  # is_cache
            return ChatResponse(
                scenario_key=key,
                answer=f"The primary root cause of the **{svc}** outage is **Cache Key Deserialization Failure & PostgreSQL Stampede** following release `v3.1.0`.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.LOG,
                        source=svc,
                        description="SerializationError: Corrupted byte header for Redis key - failed to deserialize cached object",
                        log_snippet="SerializationError: Corrupted byte header for Redis key",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.METRIC,
                        source="redis/cache_hit_ratio",
                        metric_name="redis/cache_hit_ratio",
                        description="redis/cache_hit_ratio collapsed from 98.5% down to 1.8%",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description="Deployment of catalog-service version v3.1.0 deployed prior to stampede",
                    ),
                ],
                inferences=[
                    "Release v3.1.0 changed binary serializer without versioned cache keys, breaking existing JSON cache entries.",
                    "98% cache miss rate directed 50x normal query volume to PostgreSQL, driving CPU to 100%.",
                ],
                recommendations=[
                    "Rollback catalog-service to v3.0.9 and purge invalid cache keys.",
                    "Implement singleflight mutex locking to coalesce concurrent database queries on cache miss.",
                ],
                confidence=0.97,
                grounded=True,
            )

    def _answer_evidence(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        resp = self._answer_root_cause(key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel)
        resp.answer = f"The strongest Observed Evidence supporting the diagnosis of **{svc}** includes {len(resp.evidence)} verified telemetry signals."
        return resp

    def _answer_changes(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        if is_oom or is_dep:
            return ChatResponse(
                scenario_key=key,
                answer=f"No recent code deployments were observed on **{svc}** during the observation window. The incident was triggered by runtime data/traffic conditions rather than a code deployment.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description="Zero deployment events recorded in the incident observation window",
                    ),
                ],
                inferences=[
                    "The failure was initiated by an external trigger (oversized payload or downstream partner latency) rather than a software deployment.",
                ],
                recommendations=[
                    "Inspect ingress traffic patterns and partner SLA metrics rather than rolling back application code.",
                ],
                confidence=0.99,
                grounded=True,
            )
        else:
            deploys = tel.deployments
            d = deploys[0] if deploys else None
            version_str = d.version if d else "recent change"
            summary_str = d.change_summary if d else "Configuration update"
            return ChatResponse(
                scenario_key=key,
                answer=f"A recent deployment **{version_str}** was applied to **{svc}** at 14:02 UTC immediately preceding the onset of telemetry anomalies.",
                evidence=[
                    EvidenceItem(
                        signal_type=SignalType.DEPLOYMENT,
                        source=svc,
                        description=f"Deployment of {svc} version {version_str}: {summary_str}",
                    ),
                    EvidenceItem(
                        signal_type=SignalType.HEALTH,
                        source=svc,
                        description=f"Service health transitioned from HEALTHY to UNHEALTHY following deployment of {version_str}",
                    ),
                ],
                inferences=[
                    f"The deployment {version_str} introduced the regression that destabilized {svc}.",
                ],
                recommendations=[
                    f"Perform zero-downtime rollback of {svc} to the previous stable revision.",
                ],
                confidence=0.98,
                grounded=True,
            )

    def _answer_impact(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        return ChatResponse(
            scenario_key=key,
            answer=f"The incident severely impacted **{svc}**, causing critical error rate elevation and degraded downstream customer transactions for approximately 25 minutes.",
            evidence=[
                EvidenceItem(
                    signal_type=SignalType.HEALTH,
                    source=svc,
                    description=f"{svc} health status reported UNHEALTHY with repeated probe failures",
                ),
                EvidenceItem(
                    signal_type=SignalType.LOG,
                    source=svc,
                    description=f"Critical error log burst observed in {svc} error stream",
                    log_snippet=tel.logs[0].message if tel.logs else "Error rate elevated",
                ),
            ],
            inferences=[
                "Customer-facing requests experienced high failure rates and increased latency during the unmitigated failure window.",
            ],
            recommendations=[
                "Monitor golden signal error rates and latency until health checks stabilize at HEALTHY.",
            ],
            confidence=0.95,
            grounded=True,
        )

    def _answer_remediation(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        return ChatResponse(
            scenario_key=key,
            answer=f"Before applying mitigation for **{svc}**, verify that the proposed changes are validated in dry-run simulation mode with zero infrastructure mutation.",
            evidence=[
                EvidenceItem(
                    signal_type=SignalType.HEALTH,
                    source=svc,
                    description=f"Active incident state for {svc} requires verification before production recovery",
                ),
            ],
            inferences=[
                "Applying remediation without dry-run validation risks compounding the service degradation.",
            ],
            recommendations=[
                "Execute the dry-run command in the AERO Safe Remediation console to verify manifest syntax.",
                "Ensure the rollback contingency plan is documented and tested before applying production changes.",
                "Confirm health probes return to HEALTHY and error rates drop to 0% as recovery targets.",
            ],
            confidence=0.95,
            grounded=True,
        )

    def _answer_next_steps(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        return ChatResponse(
            scenario_key=key,
            answer=f"The safest next operational step for **{svc}** is to review the five-whys causal chain, inspect dry-run simulation output, and prepare the rollback plan.",
            evidence=[
                EvidenceItem(
                    signal_type=SignalType.HEALTH,
                    source=svc,
                    description=f"Current service {svc} is in degraded state and awaiting mitigation verification",
                ),
            ],
            inferences=[
                "Diagnostic evidence is sufficient to proceed with safe, verified remediation.",
            ],
            recommendations=[
                "1. Review the Stage 4D Evidence Grounding scorecard to ensure 100% telemetry backing.",
                "2. Run the Safe Remediation simulator in dry-run mode.",
                "3. Monitor post-remediation golden signal metrics to verify recovery.",
            ],
            confidence=0.95,
            grounded=True,
        )

    def _answer_missing_evidence(self, key, svc, is_oom, is_db, is_cfg, is_dep, is_cache, tel):
        return ChatResponse(
            scenario_key=key,
            answer=f"The primary causal path for **{svc}** is well-grounded in telemetry. However, certain secondary telemetry signals were not present in the observation window.",
            evidence=[
                EvidenceItem(
                    signal_type=SignalType.HEALTH,
                    source=svc,
                    description=f"Observed telemetry window contains logs, golden metrics, and health checks for {svc}",
                ),
            ],
            inferences=[
                "Fine-grained distributed trace spans for downstream third-party internal timings were unobserved.",
                "Detailed OS-level thread dump profiles were not captured during the initial memory/connection spike.",
            ],
            recommendations=[
                "Enable OpenTelemetry trace context propagation across all external client HTTP calls.",
                "Configure automated thread dump capture on high latency alerts.",
            ],
            confidence=0.90,
            grounded=True,
        )

    def _answer_unsupported(self, key, svc, question):
        return ChatResponse(
            scenario_key=key,
            answer=f"No telemetry or diagnostic evidence for '{question}' was observed in the active **{svc}** incident dataset. Telemetry in this observation window is focused strictly on the active incident signals.",
            evidence=[],
            inferences=[
                f"The topic '{question}' is not present in the active {svc} telemetry, logs, metrics, or deployment records.",
            ],
            recommendations=[
                f"Please ask a question related to the active incident context ({svc}).",
            ],
            confidence=0.99,
            grounded=True,
        )


class VertexAiCopilotEngine(BaseCopilotEngine):
    """Live Google Cloud Vertex AI Gemini reasoning engine for SRE Copilot (Opt-in)."""

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

    def ask(
        self,
        incident: Incident,
        diagnostic_report: AeroDiagnosticReport | None,
        timeline: IncidentTimeline | None,
        question: str,
        scenario_key: str,
    ) -> ChatResponse:
        self._ensure_init()
        assert self._client is not None
        from google.genai import types

        prompt = build_copilot_prompt(incident, diagnostic_report, timeline, question)

        generate_config = types.GenerateContentConfig(
            system_instruction=COPILOT_SYSTEM_INSTRUCTION,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ChatResponse,
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=generate_config,
        )

        raw_text = response.text
        if not raw_text:
            raise ValueError("Vertex AI returned an empty response.")

        chat_resp = ChatResponse.model_validate_json(raw_text)
        chat_resp.scenario_key = scenario_key

        # Validate grounding
        is_grounded, failed_claims = CopilotGroundingVerifier.verify(chat_resp, incident)
        chat_resp.grounded = is_grounded
        chat_resp.failed_claims = failed_claims

        return chat_resp


def get_copilot_engine(provider: str | None = None) -> BaseCopilotEngine:
    """Factory returning the configured SRE Copilot engine."""
    mode = (provider or config.diagnostic_provider).lower()
    if mode in ("vertex", "live", "gemini"):
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                return VertexAiCopilotEngine()
            except Exception:  # noqa: BLE001
                return MockCopilotEngine()
        return MockCopilotEngine()
    return MockCopilotEngine()

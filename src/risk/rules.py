"""Deterministic risk rules and heuristic evaluators for AERO Pre-Deployment Risk Advisor.

Features:
1. 18 Generic SRE Deployment Safety Rules (RISK-RES, RISK-POOL, RISK-TIMEOUT, RISK-PROBE, RISK-ROLLBACK, RISK-CONFIG, RISK-DRIFT, RISK-SERVICE)
2. Diagnosis-Aware Recurrence Prevention Rules (RISK-PREV-001 through RISK-PREV-005)
"""

from __future__ import annotations

from typing import Any

from src.schemas.incident import Incident
from src.schemas.risk import (
    DiagnosisAlignmentInfo,
    DiagnosisContext,
    ProposedChange,
    RecurrencePrediction,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)

# Critical Tier-1 Services
TIER_1_SERVICES = {"order-service", "checkout-service", "payment-service", "auth-service"}


def _get_val(change: ProposedChange, *keys: str, default: Any = None) -> Any:
    """Extract parameter value from ProposedChange direct attributes or parameters dict."""
    for k in keys:
        if hasattr(change, k):
            v = getattr(change, k)
            if v is not None:
                return v
        if change.parameters and k in change.parameters:
            v = change.parameters[k]
            if v is not None:
                return v
    return default


# =============================================================================
# 1. GENERIC RULES (18 PRESERVED RULES)
# =============================================================================


def check_resource_limits(change: ProposedChange, incident: Incident | None = None) -> list[RiskFinding]:
    """Evaluate resource limit regressions, missing constraints, and telemetry baseline mismatches."""
    findings: list[RiskFinding] = []
    env = change.environment.lower()

    # Rule 1: Request exceeds limit (Memory)
    mem_req = _get_val(change, "memory_request_mb", "memory_request")
    mem_lim = _get_val(change, "memory_limit_mb", "memory_limit")
    if mem_req is not None and mem_lim is not None:
        try:
            req_val = float(mem_req)
            lim_val = float(mem_lim)
            if req_val > lim_val:
                findings.append(
                    RiskFinding(
                        rule_id="RISK-RES-001",
                        title="Resource Request Exceeds Hard Limit",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.RESOURCE_LIMITS,
                        observed_facts=[
                            f"Proposed memory request ({req_val:.0f} MB) exceeds memory limit ({lim_val:.0f} MB)."
                        ],
                        derived_risk=(
                            "Kubernetes pod specification will fail admission validation or encounter "
                            "immediate node scheduling rejections and eviction conflicts."
                        ),
                        recommendations=[
                            "Ensure container resource request is less than or equal to resource limit.",
                            "Set request to expected baseline consumption and limit to peak burst headroom.",
                        ],
                        score_impact=35,
                    )
                )
        except (ValueError, TypeError):
            pass

    # Rule 1-CPU: CPU Request exceeds limit
    cpu_req = _get_val(change, "cpu_request_cores", "cpu_request")
    cpu_lim = _get_val(change, "cpu_limit_cores", "cpu_limit")
    if cpu_req is not None and cpu_lim is not None:
        try:
            req_c = float(cpu_req)
            lim_c = float(cpu_lim)
            if req_c > lim_c:
                findings.append(
                    RiskFinding(
                        rule_id="RISK-RES-001-CPU",
                        title="CPU Request Exceeds CPU Limit",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.RESOURCE_LIMITS,
                        observed_facts=[
                            f"Proposed CPU request ({req_c:.2f} cores) exceeds CPU limit ({lim_c:.2f} cores)."
                        ],
                        derived_risk="Pod specification will be rejected by Kubernetes API server.",
                        recommendations=["Adjust CPU request to be <= CPU limit."],
                        score_impact=30,
                    )
                )
        except (ValueError, TypeError):
            pass

    # Rule 2: Missing memory/CPU constraints in production
    if env == "production" and change.change_type in ["deployment", "resource"]:
        has_mem_lim = mem_lim is not None and float(mem_lim or 0) > 0
        if not has_mem_lim:
            findings.append(
                RiskFinding(
                    rule_id="RISK-RES-002",
                    title="Missing Container Memory Limit in Production",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.RESOURCE_LIMITS,
                    observed_facts=[
                        "No memory_limit_mb defined in production deployment configuration."
                    ],
                    derived_risk=(
                        "An uncapped container process can consume unbounded node memory during traffic surges, "
                        "triggering kernel OOM-killer to terminate neighboring pods."
                    ),
                    recommendations=[
                        "Define explicit memory_limit_mb (e.g. 2048 MB) and memory_request_mb.",
                        "Enforce Kubernetes namespace LimitRange policies.",
                    ],
                    score_impact=25,
                )
            )

    # Rule 3: Memory Limit Below Active Incident Telemetry Peak / Saturated Workload
    if incident and mem_lim is not None:
        affected_svc = getattr(incident.metadata, "affected_service", "") or ""
        if change.service.lower() == affected_svc.lower():
            peak_pct = 0.0
            peak_memory_mb = 0.0
            metric_source = ""
            for series in incident.telemetry.metrics:
                if "memory" in series.metric_name.lower():
                    metric_source = series.metric_name
                    for pt in series.points:
                        if series.unit == "percent":
                            peak_pct = max(peak_pct, pt.value)
                        else:
                            val_mb = pt.value / (1024 * 1024) if pt.value > 1000000 else pt.value
                            peak_memory_mb = max(peak_memory_mb, val_mb)

            try:
                lim_val = float(mem_lim)
                is_under_provisioned = False
                fact_msg = ""
                if peak_pct >= 85.0 and lim_val < 1024:
                    is_under_provisioned = True
                    fact_msg = f"Active incident observed memory utilization peaking at {peak_pct:.1f}% ({metric_source}); proposed limit is only {lim_val:.0f} MB."
                elif peak_memory_mb > 0 and lim_val < peak_memory_mb:
                    is_under_provisioned = True
                    fact_msg = f"Proposed limit ({lim_val:.0f} MB) is lower than active telemetry peak consumption ({peak_memory_mb:.0f} MB, {metric_source})."

                if is_under_provisioned:
                    findings.append(
                        RiskFinding(
                            rule_id="RISK-RES-003",
                            title="Proposed Memory Limit Below Active Telemetry Peak",
                            severity=RiskSeverity.CRITICAL,
                            category=RiskCategory.RESOURCE_LIMITS,
                            observed_facts=[
                                f"Proposed limit: {lim_val:.0f} MB for {change.service}.",
                                fact_msg,
                            ],
                            derived_risk=(
                                f"The proposed container memory limit ({lim_val:.0f} MB) is insufficient for the active "
                                f"workload footprint. Under identical traffic, this deployment will immediately trigger "
                                "OOMKilled pod crash loops."
                            ),
                            recommendations=[
                                "Increase memory limit to at least 2048 MB to provide sufficient heap headroom.",
                                "Validate JVM heap parameters (-Xmx) are configured within cgroup limits.",
                            ],
                            score_impact=35,
                        )
                    )
            except (ValueError, TypeError):
                pass

    # Rule 4: Unusually Large Resource Increase (>300% jump)
    prev_mem = _get_val(change, "previous_memory_limit_mb")
    if prev_mem is not None and mem_lim is not None:
        try:
            prev_val = float(prev_mem)
            new_val = float(mem_lim)
            if prev_val > 0 and (new_val / prev_val) >= 4.0:  # 300%+ increase
                findings.append(
                    RiskFinding(
                        rule_id="RISK-RES-004",
                        title="Unusually Large Resource Allocation Spike (>300%)",
                        severity=RiskSeverity.MEDIUM,
                        category=RiskCategory.RESOURCE_LIMITS,
                        observed_facts=[
                            f"Memory limit scaled from {prev_val:.0f} MB to {new_val:.0f} MB ({(new_val/prev_val)*100:.0f}% of baseline)."
                        ],
                        derived_risk=(
                            "Drastic vertical scaling without documented traffic increase often masks memory leaks "
                            "or inefficient caching instead of resolving root causes, inflating cluster cost."
                        ),
                        recommendations=[
                            "Conduct memory profiler / heap dump review before 4x vertical expansion.",
                            "Evaluate Horizontal Pod Autoscaling (HPA) instead of oversized static pod footprints.",
                        ],
                        score_impact=15,
                    )
                )
        except (ValueError, TypeError):
            pass

    return findings


def check_database_pool(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate database / worker connection pool size constraints."""
    findings: list[RiskFinding] = []
    env = change.environment.lower()

    pool_size = _get_val(change, "pool_max", "pool_max_size", "db_pool_size", "max_connections")
    if pool_size is not None:
        try:
            val = int(pool_size)
            if val < 5 and env == "production":
                findings.append(
                    RiskFinding(
                        rule_id="RISK-POOL-001",
                        title="Severely Constrained Database Connection Pool (< 5)",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.DATABASE_POOL,
                        observed_facts=[
                            f"Proposed pool size is {val} connections in production environment."
                        ],
                        derived_risk=(
                            "Concurrent request volume will instantly exhaust available connections, causing request "
                            "threads to block in the pool acquisition queue until client timeouts occur."
                        ),
                        recommendations=[
                            "Increase pool_max_size to at least 20-50 connections for production services.",
                            "Implement connection pool metrics and acquisition timeout alerting.",
                        ],
                        score_impact=35,
                    )
                )
            elif val < 10 and change.service.lower() in TIER_1_SERVICES and env == "production":
                findings.append(
                    RiskFinding(
                        rule_id="RISK-POOL-002",
                        title="Suboptimal Pool Size for Tier-1 Service",
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.DATABASE_POOL,
                        observed_facts=[
                            f"Pool size configured to {val} on critical service '{change.service}'."
                        ],
                        derived_risk=(
                            "Under moderate traffic spikes, a pool size under 10 creates latency queuing bottlenecks."
                        ),
                        recommendations=[
                            "Scale pool size to match peak concurrent request capacity.",
                            "Consider connection pooling middleware (e.g. PgBouncer / ProxySQL).",
                        ],
                        score_impact=20,
                    )
                )
        except (ValueError, TypeError):
            pass

    return findings


def check_timeouts_and_dependencies(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate timeout configurations and cascading failure risks."""
    findings: list[RiskFinding] = []

    timeout_ms = _get_val(change, "timeout_ms", "client_timeout_ms")
    timeout_sec = _get_val(change, "timeout_seconds")
    if timeout_ms is None and timeout_sec is not None:
        try:
            timeout_ms = int(float(timeout_sec) * 1000)
        except (ValueError, TypeError):
            pass

    if timeout_ms is not None:
        try:
            t_val = int(timeout_ms)
            if t_val == 0:
                findings.append(
                    RiskFinding(
                        rule_id="RISK-TIMEOUT-001",
                        title="Infinite Downstream Timeout (timeout_ms = 0)",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.TIMEOUTS_DEPENDENCIES,
                        observed_facts=["Timeout parameter is set to 0 (no timeout / infinite wait)."],
                        derived_risk=(
                            "If a downstream dependency halts or deadlocks, client threads will hang indefinitely, "
                            "consuming socket descriptors and worker threads until total service starvation."
                        ),
                        recommendations=[
                            "Set an explicit bounded timeout (e.g. 2000-5000 ms).",
                            "Enforce circuit breaker trip thresholds.",
                        ],
                        score_impact=30,
                    )
                )
            elif t_val >= 30000:
                findings.append(
                    RiskFinding(
                        rule_id="RISK-TIMEOUT-002",
                        title="Excessive Downstream RPC Timeout (>= 30s)",
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.TIMEOUTS_DEPENDENCIES,
                        observed_facts=[f"Configured RPC timeout is {t_val} ms (>= 30,000 ms threshold)."],
                        derived_risk=(
                            "Long timeouts allow slow or degraded downstream dependencies to hold caller connections "
                            "open for 30+ seconds, amplifying blast radius across upstream microservices."
                        ),
                        recommendations=[
                            "Reduce timeout to <= 3000 ms with bounded exponential retries.",
                            "Implement client-side bulkhead isolation.",
                        ],
                        score_impact=20,
                    )
                )
        except (ValueError, TypeError):
            pass

    # Downstream timeout > Upstream timeout
    downstream_t = _get_val(change, "downstream_timeout_ms")
    upstream_t = _get_val(change, "upstream_timeout_ms")
    if downstream_t is not None and upstream_t is not None:
        try:
            d_val = int(downstream_t)
            u_val = int(upstream_t)
            if d_val > u_val:
                findings.append(
                    RiskFinding(
                        rule_id="RISK-TIMEOUT-003",
                        title="Downstream Timeout Exceeds Upstream Client Timeout",
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.TIMEOUTS_DEPENDENCIES,
                        observed_facts=[
                            f"Downstream call timeout: {d_val} ms.",
                            f"Upstream client timeout: {u_val} ms.",
                        ],
                        derived_risk=(
                            "The upstream client will time out and abort while downstream continues processing, "
                            "generating phantom backend load with zero user benefit."
                        ),
                        recommendations=[
                            "Set downstream timeout strictly lower than upstream caller timeout (e.g. downstream <= 0.7 * upstream).",
                            "Propagate cancellation headers via gRPC/HTTP context deadlines.",
                        ],
                        score_impact=25,
                    )
                )
        except (ValueError, TypeError):
            pass

    return findings


def check_health_and_readiness(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate health check, readiness probe, and startup safeguards."""
    findings: list[RiskFinding] = []
    env = change.environment.lower()

    readiness = _get_val(change, "readiness_probe_enabled")
    if readiness is False and env == "production":
        findings.append(
            RiskFinding(
                rule_id="RISK-PROBE-001",
                title="Readiness Probe Explicitly Disabled in Production",
                severity=RiskSeverity.HIGH,
                category=RiskCategory.HEALTH_READINESS,
                observed_facts=["readiness_probe_enabled is set to False in production deployment."],
                derived_risk=(
                    "Kubernetes will route production traffic to newly started pods immediately, before "
                    "the application has finished initializing or warming caches, producing 502/503 errors."
                ),
                recommendations=[
                    "Enable HTTP/TCP readiness probe at /healthz/ready.",
                    "Configure initialDelaySeconds and periodSeconds for graceful warmup.",
                ],
                score_impact=25,
            )
        )

    init_delay = _get_val(change, "liveness_initial_delay_seconds")
    if init_delay is not None:
        try:
            delay_val = int(init_delay)
            if delay_val < 5 and env == "production":
                findings.append(
                    RiskFinding(
                        rule_id="RISK-PROBE-002",
                        title="Aggressive Liveness Initial Delay (< 5s)",
                        severity=RiskSeverity.MEDIUM,
                        category=RiskCategory.HEALTH_READINESS,
                        observed_facts=[f"Liveness initialDelaySeconds is configured to {delay_val}s."],
                        derived_risk=(
                            "If container startup or JVM initialization takes longer than 5 seconds, Kubernetes will "
                            "falsely declare the pod dead and enter a crash restart loop."
                        ),
                        recommendations=[
                            "Increase liveness initialDelaySeconds to >= 15-30s.",
                            "Use Kubernetes startupProbe for slow-initializing workloads.",
                        ],
                        score_impact=15,
                    )
                )
        except (ValueError, TypeError):
            pass

    return findings


def check_rollback_strategy(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate rollback preparedness and image tagging hygiene."""
    findings: list[RiskFinding] = []
    env = change.environment.lower()

    # Check unversioned latest tag
    image_tag = _get_val(change, "image_tag", default="") or ""
    if str(image_tag).lower() == "latest" and env == "production":
        findings.append(
            RiskFinding(
                rule_id="RISK-ROLLBACK-001",
                title="Mutable ':latest' Image Tag in Production",
                severity=RiskSeverity.HIGH,
                category=RiskCategory.ROLLBACK_STRATEGY,
                observed_facts=["Container image tag is set to ':latest'."],
                derived_risk=(
                    "Using mutable ':latest' tags causes non-deterministic deployments across nodes and prevents "
                    "reliable, rapid rollback to an immutable prior release."
                ),
                recommendations=[
                    "Use immutable semantic versioning or commit SHA tags (e.g. :v2.4.1 or :sha-a7f3b8c).",
                    "Pin container digest SHA256 in deployment manifests.",
                ],
                score_impact=20,
            )
        )

    # Missing rollback plan on production deployment
    has_rollback = bool(change.rollback_plan or _get_val(change, "rollback_version"))
    if not has_rollback and env == "production" and change.change_type in ["deployment", "config"]:
        findings.append(
            RiskFinding(
                rule_id="RISK-ROLLBACK-002",
                title="Missing Rollback Plan / Previous Version Pin",
                severity=RiskSeverity.MEDIUM,
                category=RiskCategory.ROLLBACK_STRATEGY,
                observed_facts=["No rollback_plan or rollback_version specified for production deployment."],
                derived_risk=(
                    "In the event of an undetected regression, the on-call engineer lacks a pre-validated "
                    "reversion target, increasing Mean Time to Recovery (MTTR)."
                ),
                recommendations=[
                    "Explicitly document rollback target version (e.g. rollback_version='v2.4.0').",
                    "Automate rollback triggers on elevated p99 latency or 5xx error rates.",
                ],
                score_impact=15,
            )
        )

    return findings


def check_dangerous_config(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate dangerous runtime flags, insecure settings, and debug logging."""
    findings: list[RiskFinding] = []
    env = change.environment.lower()

    if env == "production":
        debug_mode = _get_val(change, "debug_mode")
        log_level = _get_val(change, "log_level", default="")
        debug_active = debug_mode is True or str(log_level).upper() == "DEBUG"
        if debug_active:
            findings.append(
                RiskFinding(
                    rule_id="RISK-CONFIG-001",
                    title="Debug Logging / Debug Mode Enabled in Production",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.DANGEROUS_CONFIG,
                    observed_facts=[
                        f"Debug flag detected: debug_mode={debug_mode}, log_level={log_level}."
                    ],
                    derived_risk=(
                        "Verbose debug logging degrades CPU and disk I/O throughput by 20-40%, risks logging sensitive "
                        "PII / auth tokens, and can rapidly fill log storage."
                    ),
                    recommendations=[
                        "Set production log level to INFO or WARN.",
                        "Disable runtime debug endpoints (/debug/pprof) in public ingress.",
                    ],
                    score_impact=25,
                )
            )

        insecure = _get_val(change, "allow_insecure_transport") is True or _get_val(change, "disable_tls") is True
        if insecure:
            findings.append(
                RiskFinding(
                    rule_id="RISK-CONFIG-002",
                    title="Insecure Transport / TLS Disabled in Production",
                    severity=RiskSeverity.CRITICAL,
                    category=RiskCategory.DANGEROUS_CONFIG,
                    observed_facts=["TLS encryption or secure transport is explicitly disabled."],
                    derived_risk="Transmitting unencrypted payloads violates compliance and exposes credentials in transit.",
                    recommendations=["Enforce TLS 1.3 for all inter-service communications."],
                    score_impact=35,
                )
            )

    return findings


def check_config_drift(change: ProposedChange, incident: Incident | None = None) -> list[RiskFinding]:
    """Evaluate configuration drift and environmental discrepancies."""
    findings: list[RiskFinding] = []

    drift_detected = _get_val(change, "config_drift_detected")
    if drift_detected is True or (
        incident
        and "drift" in (getattr(incident.metadata, "impact_summary", "") or "").lower()
        and change.service.lower() == (getattr(incident.metadata, "affected_service", "") or "").lower()
    ):
        findings.append(
            RiskFinding(
                rule_id="RISK-DRIFT-001",
                title="Configuration Drift / Discrepancy on Target Service",
                severity=RiskSeverity.HIGH,
                category=RiskCategory.CONFIG_DRIFT,
                observed_facts=[
                    f"Active configuration drift identified on service '{change.service}'."
                ],
                derived_risk=(
                    "Applying new configuration on top of un-reconciled drifted infrastructure causes unpredictable "
                    "system state transitions and invalidates staging test assumptions."
                ),
                recommendations=[
                    "Reconcile running state against GitOps repository single source of truth.",
                    "Execute a dry-run diff before applying live changes.",
                ],
                score_impact=25,
            )
        )

    return findings


def check_critical_service(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate blast radius on revenue-critical tier-1 microservices."""
    findings: list[RiskFinding] = []

    if change.service.lower() in TIER_1_SERVICES and change.environment.lower() == "production":
        findings.append(
            RiskFinding(
                rule_id="RISK-SERVICE-001",
                title=f"High Blast Radius Change to Tier-1 Service ({change.service})",
                severity=RiskSeverity.MEDIUM,
                category=RiskCategory.CRITICAL_SERVICE,
                observed_facts=[
                    f"Target service '{change.service}' is classified in Tier-1 critical path."
                ],
                derived_risk=(
                    "Any disruption on this service directly halts checkout transactions and impacts customer SLA."
                ),
                recommendations=[
                    "Perform canary rollout with 5% traffic split before 100% promotion.",
                    "Monitor Golden Signals for 15 minutes post-deployment.",
                ],
                score_impact=10,
            )
        )

    return findings


def check_insufficient_input(change: ProposedChange) -> list[RiskFinding]:
    """Evaluate whether the change specification is too sparse to evaluate meaningfully."""
    findings: list[RiskFinding] = []

    desc = change.description.strip()
    has_params = bool(change.parameters) or any(
        getattr(change, k, None) is not None
        for k in [
            "memory_limit_mb",
            "cpu_limit",
            "concurrency",
            "pool_max",
            "timeout_seconds",
            "image_tag",
        ]
    )

    if len(desc) < 5 and not has_params:
        findings.append(
            RiskFinding(
                rule_id="RISK-INSUFFICIENT-001",
                title="Insufficient Change Specification Details",
                severity=RiskSeverity.LOW,
                category=RiskCategory.INSUFFICIENT_INPUT,
                observed_facts=["Change description is minimal and no structured parameters were provided."],
                derived_risk=(
                    "Without structured parameters (memory limits, connection pool, timeouts, probe settings), "
                    "only high-level heuristic evaluation can be performed."
                ),
                recommendations=[
                    "Provide explicit parameters (e.g. memory_limit_mb, pool_size, timeout_ms).",
                    "Include deployment diff or configuration keys for deep verification.",
                ],
                score_impact=5,
            )
        )

    return findings


# =============================================================================
# 2. DIAGNOSIS-AWARE RECURRENCE PREVENTION RULES
# =============================================================================


def evaluate_diagnosis_prevention_rules(
    change: ProposedChange,
    incident: Incident | None = None,
    diag_context: DiagnosisContext | None = None,
) -> tuple[list[RiskFinding], DiagnosisAlignmentInfo, RecurrencePrediction, list[str]]:
    """Evaluate proposed change against verified incident diagnosis, observed telemetry, and AERO recommendations."""
    prevention_findings: list[RiskFinding] = []
    evidence_used: list[str] = []

    # 1. Extract incident metadata & telemetry facts
    affected_svc = getattr(incident.metadata, "affected_service", "") if incident else ""
    target_svc = change.service or getattr(change, "target_service", "") or ""
    is_affected_service = bool(affected_svc and target_svc.lower() == affected_svc.lower())

    # Extract quantitative facts from telemetry
    peak_mem_pct = 0.0
    peak_mem_mb = 0.0
    metric_source = ""
    oom_log_count = 0
    if incident and incident.telemetry:
        for series in incident.telemetry.metrics:
            if "memory" in series.metric_name.lower():
                metric_source = series.metric_name
                for pt in series.points:
                    if series.unit == "percent":
                        peak_mem_pct = max(peak_mem_pct, pt.value)
                    else:
                        val_mb = pt.value / (1024 * 1024) if pt.value > 1000000 else pt.value
                        peak_mem_mb = max(peak_mem_mb, val_mb)
        for log in incident.telemetry.logs:
            msg = log.message.lower()
            if "oom" in msg or "killed" in msg or "out of memory" in msg:
                oom_log_count += 1

    # Extract diagnosis details
    root_cause = ""
    diag_category = ""
    aero_recs: list[str] = []
    if diag_context:
        root_cause = diag_context.root_cause or ""
        diag_category = (diag_context.diagnosis_category or "").upper()
        aero_recs = diag_context.recommendations or diag_context.mitigation_actions or []
        evidence_used.extend(diag_context.observed_evidence or [])
        evidence_used.extend(diag_context.telemetry_facts or [])
    elif incident:
        root_cause = getattr(incident.metadata, "impact_summary", "") or getattr(incident.metadata, "title", "")
        diag_category = getattr(incident.metadata, "severity", "CRITICAL")
        if peak_mem_pct >= 85.0 or oom_log_count > 0:
            diag_category = "RESOURCE_EXHAUSTION_MEMORY"
            root_cause = "Container memory exhaustion triggering Linux cgroup OOM-killer"
            aero_recs = [
                "Increase container memory limit to >= 2048 MB to provide heap headroom",
                "Maintain bounded worker concurrency (e.g. 10 workers)",
                "Configure automated canary rollback triggers",
            ]

    if peak_mem_pct > 0:
        evidence_used.append(f"Observed peak memory utilization: {peak_mem_pct:.2f}% ({metric_source})")
    if peak_mem_mb > 0:
        evidence_used.append(f"Observed peak memory footprint: {peak_mem_mb:.0f} MB")
    if oom_log_count > 0:
        evidence_used.append(f"Recorded {oom_log_count} kernel/cgroup OOMKilled eviction events")

    # Parameters from proposed change
    mem_lim = _get_val(change, "memory_limit_mb", "memory_limit")
    concurrency = _get_val(change, "concurrency", "worker_count", "workers", "thread_pool_size")
    pool_max = _get_val(change, "pool_max", "pool_max_size", "db_pool_size")
    has_rollback = bool(change.rollback_plan or _get_val(change, "rollback_version"))

    # Determine failure mode type
    is_memory_failure = (
        "memory" in diag_category.lower()
        or "oom" in diag_category.lower()
        or "resource_exhaustion" in diag_category.lower()
        or "memory" in root_cause.lower()
        or "oom" in root_cause.lower()
        or peak_mem_pct >= 85.0
        or oom_log_count > 0
    )

    # Check parameter distribution
    has_mem_param = mem_lim is not None and float(mem_lim or 0) > 0
    has_conc_param = concurrency is not None
    has_other_params = pool_max is not None or _get_val(change, "timeout_ms") is not None or _get_val(change, "log_level") is not None
    is_unrelated_config_only = has_other_params and not has_mem_param and not has_conc_param

    # -------------------------------------------------------------------------
    # RULE A: RISK-PREV-001 — ROOT CAUSE ALIGNMENT (Memory Pressure)
    # -------------------------------------------------------------------------
    if is_memory_failure and is_affected_service and not is_unrelated_config_only:
        has_adequate_memory = False
        if mem_lim is not None:
            try:
                has_adequate_memory = float(mem_lim) >= 2048
            except (ValueError, TypeError):
                pass

        if not has_adequate_memory:
            cur_val = float(mem_lim) if mem_lim is not None else 0
            findings_facts = [
                f"Diagnosed root cause on '{target_svc}': {root_cause or 'Memory exhaustion / OOMKilled'}.",
            ]
            if peak_mem_pct > 0:
                findings_facts.append(f"Observed telemetry memory peak reached {peak_mem_pct:.1f}% ({peak_mem_mb:.0f} MB).")
            findings_facts.append(
                f"Proposed memory limit ({cur_val:.0f} MB) does not provide recommended headroom (>= 2048 MB)."
            )

            prevention_findings.append(
                RiskFinding(
                    rule_id="RISK-PREV-001",
                    title="Proposed Change Does Not Address Diagnosed Memory Exhaustion",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.RESOURCE_LIMITS,
                    observed_facts=findings_facts,
                    derived_risk=(
                        "Deploying without sufficient memory headroom leaves the target container vulnerable "
                        "to identical heap saturation and OOM-killer termination under production load."
                    ),
                    recommendations=[
                        "Increase memory_limit_mb to at least 2048 MB to accommodate peak heap demands.",
                        "Align container cgroup limits with JVM/runtime heap allocations.",
                    ],
                    score_impact=30,
                )
            )

    # -------------------------------------------------------------------------
    # RULE B: RISK-PREV-002 — RECURRENCE PREDICTION (Severe Under-Provisioning)
    # -------------------------------------------------------------------------
    if is_memory_failure and is_affected_service and mem_lim is not None:
        try:
            lim_val = float(mem_lim)
            if (peak_mem_pct >= 85.0 or peak_mem_mb >= 1024 or oom_log_count > 0) and lim_val <= 1024:
                prevention_findings.append(
                    RiskFinding(
                        rule_id="RISK-PREV-002",
                        title="High Recurrence Risk: Memory Limit Below Observed Saturation Peak",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.RESOURCE_LIMITS,
                        observed_facts=[
                            f"Proposed container memory limit is only {lim_val:.0f} MB.",
                            f"Incident telemetry recorded saturated memory peak of {peak_mem_pct:.1f}% (~{peak_mem_mb:.0f} MB) with {oom_log_count} OOM events.",
                        ],
                        derived_risk=(
                            f"The proposed memory boundary ({lim_val:.0f} MB) is strictly below the actual workload "
                            "consumption observed during the incident. Pods will experience immediate OOMKilled crash loops."
                        ),
                        recommendations=[
                            "Increase memory limit to >= 2048 MB to provide safety margin above observed peak.",
                        ],
                        score_impact=40,
                    )
                )
        except (ValueError, TypeError):
            pass

    # -------------------------------------------------------------------------
    # RULE C: RISK-PREV-003 — CONCURRENCY MULTIPLICATION UNDER RESOURCE PRESSURE
    # -------------------------------------------------------------------------
    if is_memory_failure and is_affected_service and concurrency is not None:
        try:
            conc_val = int(concurrency)
            lim_val = float(mem_lim or 1024)
            # Baseline concurrency is 10; scaling to >= 50 or 100 without >= 4096MB memory is dangerous
            if conc_val >= 50 and lim_val < 4096:
                prevention_findings.append(
                    RiskFinding(
                        rule_id="RISK-PREV-003",
                        title="Aggressive Concurrency Scaling Without Proportional Memory Headroom",
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.RESOURCE_LIMITS,
                        observed_facts=[
                            f"Diagnosed failure mode: {root_cause or 'Memory exhaustion'}.",
                            f"Proposed change increases worker concurrency to {conc_val} (10x baseline).",
                            f"Container memory limit ({lim_val:.0f} MB) is insufficient for {conc_val} concurrent worker threads.",
                        ],
                        derived_risk=(
                            f"Multiplying concurrent worker threads to {conc_val} dramatically inflates active per-thread "
                            "heap buffers, exponentially accelerating memory exhaustion and triggering instantaneous OOM termination."
                        ),
                        recommendations=[
                            "Maintain bounded worker concurrency (e.g. 10 workers) until heap consumption is profiled.",
                            "If high concurrency is mandatory, allocate at least 4096 MB memory and scale horizontally.",
                        ],
                        score_impact=35,
                    )
                )
        except (ValueError, TypeError):
            pass

    # -------------------------------------------------------------------------
    # RULE D: RISK-PREV-004 — CONTRADICTION OF AERO RECOMMENDATIONS
    # -------------------------------------------------------------------------
    if is_memory_failure and is_affected_service and concurrency is not None:
        try:
            conc_val = int(concurrency)
            if conc_val > 20:
                prevention_findings.append(
                    RiskFinding(
                        rule_id="RISK-PREV-004",
                        title="Proposed Change Contradicts AERO Diagnostic Mitigation Guidance",
                        severity=RiskSeverity.HIGH,
                        category=RiskCategory.DANGEROUS_CONFIG,
                        observed_facts=[
                            "AERO Incident Recommendation: Maintain bounded concurrency (10 workers) and increase memory headroom.",
                            f"Proposed Change: Expands worker concurrency to {conc_val}.",
                        ],
                        derived_risk=(
                            "Applying configurations that move counter to verified incident findings undermines stability "
                            "and directly recreates the preconditions of the active failure."
                        ),
                        recommendations=[
                            "Align concurrency limits with AERO recommended bounds (10-20 workers).",
                        ],
                        score_impact=25,
                    )
                )
        except (ValueError, TypeError):
            pass

    # -------------------------------------------------------------------------
    # RULE E: RISK-PREV-005 — UNRELATED CHANGE NOT ADDRESSING ROOT CAUSE
    # -------------------------------------------------------------------------
    if is_memory_failure and is_affected_service:
        # Check if the proposed change modified secondary parameters (pool, timeout, log) but ignored memory
        has_mem_param = mem_lim is not None and float(mem_lim or 0) > 0
        has_conc_param = concurrency is not None
        has_other_params = pool_max is not None or _get_val(change, "timeout_ms") is not None or _get_val(change, "log_level") is not None
        if has_other_params and not has_mem_param and not has_conc_param:
            prevention_findings.append(
                RiskFinding(
                    rule_id="RISK-PREV-005",
                    title="Proposed Deployment Does Not Address Diagnosed Incident Root Cause",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.RESOURCE_LIMITS,
                    observed_facts=[
                        f"Active incident root cause is {root_cause or 'Memory exhaustion'}.",
                        "Proposed configuration modifies connection/timeout parameters but omits corrective memory limit adjustments.",
                    ],
                    derived_risk=(
                        "The proposed deployment will deploy cleanly but fails to remediate the underlying incident vulnerability, "
                        "leaving the service exposed to recurrence under peak load."
                    ),
                    recommendations=[
                        "Include corrective memory limits (memory_limit_mb: 2048) in this deployment package.",
                    ],
                    score_impact=20,
                )
            )

    # -------------------------------------------------------------------------
    # SYNTHESIZE DIAGNOSIS ALIGNMENT & RECURRENCE PREDICTION
    # -------------------------------------------------------------------------
    has_crit_prev = any(f.severity == RiskSeverity.CRITICAL for f in prevention_findings)
    has_high_prev = any(f.severity == RiskSeverity.HIGH for f in prevention_findings)

    # Recurrence Prediction
    sat_desc = f"{peak_mem_pct:.1f}% peak ({peak_mem_mb:.0f} MB)" if peak_mem_mb > 0 else f"{peak_mem_pct:.1f}% peak saturation"
    if has_crit_prev:
        rec_risk = RiskSeverity.CRITICAL
        likely_rec = True
        rec_reason = (
            f"Proposed configuration remains below observed saturation conditions ({sat_desc}). "
            "High probability of immediate recurrence under identical production traffic."
        )
    elif has_high_prev:
        rec_risk = RiskSeverity.HIGH
        likely_rec = True
        rec_reason = (
            "Proposed change modifies configuration but does not adequately provide memory headroom or bounds concurrency. "
            "Likely recurrence under peak workload surges."
        )
    elif is_memory_failure and is_affected_service and mem_lim is not None and float(mem_lim or 0) >= 2048:
        rec_risk = RiskSeverity.LOW
        likely_rec = False
        rec_reason = (
            "Proposed change addresses the diagnosed memory exhaustion mechanism and provides sufficient resource headroom "
            f"(2048 MB) well above observed peak saturation conditions ({peak_mem_pct:.1f}%)."
        )
    elif not is_affected_service and incident:
        rec_risk = RiskSeverity.LOW
        likely_rec = False
        rec_reason = "Target service is isolated from active incident blast radius."
    else:
        rec_risk = RiskSeverity.LOW
        likely_rec = False
        rec_reason = "No recurrence risk patterns detected against current incident evidence."

    predicted_recurrence = RecurrencePrediction(
        risk=rec_risk,
        likely_recurrence=likely_rec,
        reason=rec_reason,
    )

    # Diagnosis Alignment Info
    is_aligned = len(prevention_findings) == 0 and bool(mem_lim and float(mem_lim or 0) >= 2048) if is_memory_failure else len(prevention_findings) == 0
    if is_aligned:
        alignment_summary = (
            f"Proposed deployment directly implements AERO incident recommendations: provides 2048 MB memory headroom, "
            f"maintains bounded concurrency, and includes {'validated rollback targets' if has_rollback else 'standard release tags'}."
        )
    else:
        alignment_summary = (
            f"Proposed deployment deviates from AERO diagnostic findings: {len(prevention_findings)} prevention risk findings detected."
        )

    obs_peak_str = (
        f"{peak_mem_pct:.1f}% ({peak_mem_mb:.0f} MB)" if peak_mem_mb > 0
        else (f"{peak_mem_pct:.1f}%" if peak_mem_pct > 0 else "Baseline nominal")
    )

    diagnosis_alignment = DiagnosisAlignmentInfo(
        root_cause=root_cause or "Diagnosed service incident",
        diagnosis_category=diag_category or "RESOURCE_EXHAUSTION_MEMORY",
        observed_peak=obs_peak_str,
        aero_recommendations=aero_recs or ["Increase memory limit to >= 2048 MB", "Maintain bounded worker concurrency"],
        is_aligned=is_aligned,
        alignment_summary=alignment_summary,
    )

    return prevention_findings, diagnosis_alignment, predicted_recurrence, evidence_used

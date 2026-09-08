"""Deterministic risk rules and heuristic evaluators for AERO Pre-Deployment Risk Advisor."""

from __future__ import annotations

from src.schemas.incident import Incident
from src.schemas.risk import ProposedChange, RiskCategory, RiskFinding, RiskSeverity

# Critical Tier-1 Services
TIER_1_SERVICES = {"order-service", "checkout-service", "payment-service", "auth-service"}


def check_resource_limits(change: ProposedChange, incident: Incident | None = None) -> list[RiskFinding]:
    """Evaluate resource limit regressions, missing constraints, and telemetry baseline mismatches."""
    findings: list[RiskFinding] = []
    params = change.parameters
    env = change.environment.lower()

    # Rule 1: Request exceeds limit
    mem_req = params.get("memory_request_mb")
    mem_lim = params.get("memory_limit_mb")
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

    cpu_req = params.get("cpu_request_cores")
    cpu_lim = params.get("cpu_limit_cores")
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
    prev_mem = params.get("previous_memory_limit_mb")
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
    params = change.parameters
    env = change.environment.lower()

    pool_size = params.get("pool_max_size") or params.get("db_pool_size") or params.get("max_connections")
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
    params = change.parameters

    timeout_ms = params.get("timeout_ms") if "timeout_ms" in params else params.get("client_timeout_ms")
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
    downstream_t = params.get("downstream_timeout_ms")
    upstream_t = params.get("upstream_timeout_ms")
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
    params = change.parameters
    env = change.environment.lower()

    if "readiness_probe_enabled" in params and not params["readiness_probe_enabled"] and env == "production":
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

    init_delay = params.get("liveness_initial_delay_seconds")
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
    params = change.parameters
    env = change.environment.lower()

    # Check unversioned latest tag
    image_tag = params.get("image_tag", "") or ""
    if image_tag.lower() == "latest" and env == "production":
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
    has_rollback = bool(change.rollback_plan or params.get("rollback_version"))
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
    params = change.parameters
    env = change.environment.lower()

    if env == "production":
        debug_active = params.get("debug_mode") is True or str(params.get("log_level", "")).upper() == "DEBUG"
        if debug_active:
            findings.append(
                RiskFinding(
                    rule_id="RISK-CONFIG-001",
                    title="Debug Logging / Debug Mode Enabled in Production",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.DANGEROUS_CONFIG,
                    observed_facts=[
                        f"Debug flag detected: debug_mode={params.get('debug_mode')}, log_level={params.get('log_level')}."
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

        if params.get("allow_insecure_transport") is True or params.get("disable_tls") is True:
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
    params = change.parameters

    if params.get("config_drift_detected") is True or (
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
    has_params = bool(change.parameters)

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

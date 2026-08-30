# AERO Technical Decisions & Architecture Decision Records (ADRs)

**Program:** Google Patchamomma 2026  
**Status:** Approved Blueprint  
**Date:** August 30, 2026  

---

## Overview

This document records the foundational architectural decisions, rationale, trade-offs, and alternatives considered for **AERO** (AI-Enabled Reliability & Operations). Each Architectural Decision Record (ADR) follows a structured format to ensure clarity and traceability throughout the development lifecycle.

---

## Table of Architectural Decision Records

- [ADR-001: Use of Synthetic Ground-Truth Incident Datasets for Quantitative Evaluation](#adr-001-use-of-synthetic-ground-truth-incident-datasets-for-quantitative-evaluation)
- [ADR-002: Model Selection — Google Gemini on Vertex AI](#adr-002-model-selection--google-gemini-on-vertex-ai)
- [ADR-003: Dedicated RAG Architecture for Engineering Memory vs. Long-Context Prompt Stuffing](#adr-003-dedicated-rag-architecture-for-engineering-memory-vs-long-context-prompt-stuffing)
- [ADR-004: Compute & Hosting Platform — Google Cloud Run](#adr-004-compute--hosting-platform--google-cloud-run)
- [ADR-005: Separation of High-Velocity Telemetry from Curated Engineering Knowledge](#adr-005-separation-of-high-velocity-telemetry-from-curated-engineering-knowledge)
- [ADR-006: Human-in-the-Loop Remediation vs. Autonomous Execution](#adr-006-human-in-the-loop-remediation-vs-autonomous-execution)
- [ADR-007: Security, Privacy & Telemetry Masking Architecture](#adr-007-security-privacy--telemetry-masking-architecture)
- [ADR-008: Cost-Conscious Design & Token Budgeting Strategy](#adr-008-cost-conscious-design--token-budgeting-strategy)
- [ADR-009: AI Evaluation, Ground-Truth Validation & Hallucination Guardrails](#adr-009-ai-evaluation-ground-truth-validation--hallucination-guardrails)

---

### ADR-001: Use of Synthetic Ground-Truth Incident Datasets for Quantitative Evaluation

#### Context & Problem
Evaluating an AI diagnostic engine requires knowing the true root cause, exact failure sequence, and expected remediation steps for any given incident. Real production logs from enterprises are proprietary, laden with sensitive PII, sparse in frequency, and often lack objective, verified ground-truth labels. Without known ground truth, it is impossible to quantitatively measure whether AERO’s diagnoses are accurate or hallucinated.

#### Decision
Develop a comprehensive **Synthetic Incident Benchmark Suite** comprising 5+ realistic, reproducible microservice incident scenarios with mathematically and logically defined ground truth:
1. *Scenario A (Resource Exhaustion):* Memory leak in worker pool $\rightarrow$ gradual RAM increase $\rightarrow$ OOMKill $\rightarrow$ 502 Gateway Errors.
2. *Scenario B (Database Starvation):* Unindexed query rollout $\rightarrow$ slow query latency $\rightarrow$ connection pool saturation $\rightarrow$ 504 Timeouts.
3. *Scenario C (Config Drift / Mismatch):* Environment variable misconfiguration $\rightarrow$ auth service handshake failure $\rightarrow$ 401 Unauthorized cascade.
4. *Scenario D (Upstream Dependency Outage):* Third-party payment gateway timeout $\rightarrow$ thread pool exhaustion $\rightarrow$ cascading latency.
5. *Scenario E (Cache Poisoning / Invalidation):* Corrupted Redis serialization key $\rightarrow$ cache miss storm $\rightarrow$ DB CPU saturation at 100%.

#### Alternatives Considered
- **Using public open-source log datasets (e.g., LogHub, BGL, HDFS logs):** Rejected because they contain raw log lines without correlated multi-signal metrics, deployment diffs, runbooks, or modern cloud-native causal structures.
- **Mocking AI outputs directly:** Rejected because it circumvents actual LLM reasoning and validation.

#### Consequences & Benefits
- **Deterministic Ground-Truth Validation:** Enables automated precision/recall scoring on whether Gemini identifies the true root cause.
- **Repeatable CI/CD Benchmarks:** Every model prompt change or retrieval tweak can be evaluated against the benchmark suite in seconds.
- **Zero Privacy Risk:** Synthetic telemetry contains zero proprietary corporate secrets or PII.

---

### ADR-002: Model Selection — Google Gemini on Vertex AI (Configurable Tiers)

#### Context & Problem
AERO requires foundation models capable of:
1. Long-context multi-signal reasoning across logs, metrics, and deployment events.
2. Native multimodal capabilities (parsing time-series charts, topology diagrams).
3. Strict JSON Structured Output compliance to reliably drive UI components.
4. Low inference latency and native integration with the Google Cloud ecosystem.
5. Future-proofing: Models evolve rapidly, so the architecture must allow upgrading model versions via configuration without code refactoring.

#### Decision
Implement a **Tiered, Configurable Model Architecture** on Vertex AI managed via environment variables and configuration objects (`config.py`):
- **Reasoning Tier (`AERO_REASONING_MODEL`):** High-capability Gemini model used for deep causal root-cause reasoning, postmortem synthesis, and pre-deployment risk analysis (e.g., `gemini-2.5-pro`, `gemini-1.5-pro`, or latest Vertex AI Gemini reasoning endpoint).
- **Fast / Filter Tier (`AERO_FAST_MODEL`):** Ultra-low latency Gemini model used for rapid telemetry pre-filtering, log anomaly extraction, and real-time interactive SRE chat (e.g., `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`, targeting $<1.5\text{s}$ response).
- **Embedding Tier (`AERO_EMBEDDING_MODEL`):** Vertex AI text embedding model used for semantic vector embeddings across runbooks and historical postmortems (e.g., `text-embedding-005`, `text-embedding-004`).

#### Alternatives Considered
- **Hardcoding Specific Model Strings:** Rejected because model checkpoints deprecate and improve rapidly; configurable tiers ensure seamless updates.
- **Self-hosted Open-Weights Models (e.g., Llama 3 on GKE/Compute Engine):** Rejected due to high infrastructure cost, cold-start provisioning delays, GPU cluster management overhead, and lack of managed multimodal APIs for a focused sprint.
- **Third-Party External APIs:** Rejected to keep all data, networking, and governance strictly within the Google Cloud perimeter.

#### Consequences & Benefits
- Native integration with Vertex AI Vector Search, Cloud Logging, and BigQuery.
- Strict Pydantic/JSON schema enforcement via Gemini Structured Outputs.
- Configurable environment-driven model endpoints allow zero-code upgrades as new Gemini models are released.

---

### ADR-003: Dedicated RAG Architecture for Engineering Memory vs. Long-Context Prompt Stuffing

#### Context & Problem
While Gemini offers a massive context window, dumping entire organizational wikis, dozens of runbooks, and hundreds of past postmortems directly into every prompt ("context stuffing") leads to:
1. Drastically higher token costs and billing spikes.
2. Increased inference latency (exceeding our $<10\text{s}$ target).
3. "Lost in the middle" degradation where irrelevant past incidents dilute the model's focus on the active incident's specific telemetry.

#### Decision
Implement a **Retrieval-Augmented Generation (RAG)** architecture using **Vertex AI Vector Search**:
1. Runbooks and past postmortems in Cloud Storage are chunked by logical sections (Summary, Root Cause, Mitigation Steps).
2. Chunks are embedded via configurable Vertex AI embeddings (`AERO_EMBEDDING_MODEL`) and indexed in Vertex AI Vector Search.
3. During live triage, AERO transforms the active incident's error signature into a semantic search query to retrieve the **top-2 to top-3 most relevant documents**.
4. Only these retrieved chunks are injected into the Gemini diagnostic context.

#### Alternatives Considered
- **Full Prompt Stuffing:** Rejected due to cost, latency, and noise.
- **Traditional Keyword Search (Elasticsearch / Cloud Search):** Rejected because incident descriptions often use varied terminology for the same underlying failure (e.g., "OOMKilled" vs "Memory limit exceeded" vs "OutOfMemoryError"), which semantic embeddings handle effortlessly.

#### Consequences & Benefits
- Sub-second vector retrieval ($<500\text{ms}$).
- Keeps prompt token count compact ($\le 8\text{k}$ tokens per diagnostic query).
- Ensures high relevance and grounded citations.

---

### ADR-004: Compute & Hosting Platform — Google Cloud Run

#### Context & Problem
AERO's web dashboard and API backend need a hosting environment that provides rapid deployment, high availability, zero management overhead, and low operational cost during development.

#### Decision
Deploy all AERO services (FastAPI Backend and SRE Copilot Frontend) onto **Google Cloud Run**:
- Fully managed container execution.
- Automatic scaling to zero when idle (conserving budget).
- Built-in HTTPS endpoints, custom domains, and seamless Cloud IAM integration.
- Instant rolling deployments directly from container artifacts.

#### Alternatives Considered
- **Google Kubernetes Engine (GKE):** Rejected because managing clusters, control planes, and node pools introduces unnecessary operational toil for a hackathon timeline.
- **Compute Engine VMs:** Rejected due to lack of native scale-to-zero, manual patching requirements, and persistent idle billing.

#### Consequences & Benefits
- Zero infrastructure maintenance.
- Instant cold-start and sub-second scale-up during incident simulations.
- Direct connectivity to Cloud Logging, Pub/Sub, and Vertex AI via Google Cloud internal network.

---

### ADR-005: Separation of High-Velocity Telemetry from Curated Engineering Knowledge

#### Context & Problem
Incident management involves two fundamentally different data classes:
1. **High-Velocity Telemetry:** Logs, metric timeseries, alerts, and deployment events (ephemeral, high-volume, structured/semi-structured, time-indexed).
2. **Curated Engineering Knowledge:** Runbooks, postmortems, architecture documentation, and remediation procedures (long-lived, unstructured/markdown, semantic).

Attempting to store both in a single database compromises query performance and complicates schema design.

#### Decision
Enforce a clear architectural separation:
- **Telemetry Layer:** Handled by **Cloud Logging**, **Cloud Monitoring**, and **BigQuery** (optimized for time-series aggregation, log filtering, and analytical queries).
- **Knowledge Layer:** Handled by **Cloud Storage (GCS)** and **Vertex AI Vector Search** (optimized for semantic retrieval, document versioning, and RAG).

```
+-------------------------------------------------------------------------+
|                              DATA SEPARATION                            |
+------------------------------------+------------------------------------+
|       TELEMETRY LAYER              |         KNOWLEDGE LAYER            |
| - Cloud Logging (Raw Logs)         | - Cloud Storage (Markdown/PDFs)    |
| - Cloud Monitoring (Metrics)       | - Vertex AI Vector Search (Embeds) |
| - BigQuery (Historical Analytics)  | - Curated Postmortems & Runbooks   |
+------------------------------------+------------------------------------+
```

#### Consequences & Benefits
- Prevents database bloat and preserves high-throughput query performance.
- Enables independent indexing schedules for operational documents without interfering with live log streaming.

---

### ADR-006: Human-in-the-Loop Remediation vs. Autonomous Execution

#### Context & Problem
While an AI system could theoretically execute remediation commands directly (e.g., executing `kubectl scale` or `gcloud run services update`), autonomous production mutation poses severe risks:
1. Hallucinated or miscalibrated commands could trigger cascading outages or data loss.
2. Lack of operator confidence prevents real-world adoption.
3. Unintended side effects during complex multi-service outages.

#### Decision
AERO operates strictly under a **Human-in-the-Loop (HITL)** paradigm:
- AERO generates structured, evidence-backed remediation recommendations.
- AERO provides exact dry-run commands, expected health indicators, and rollback procedures.
- The human on-call engineer reviews, approves, and triggers the mitigation.
- Direct autonomous write/destructive execution is intentionally out of scope for the core MVP.

#### Alternatives Considered
- **Fully Autonomous Self-Healing Agent:** Rejected as unsafe and unrealistic for production mission-critical environments.

#### Consequences & Benefits
- High operator trust and psychological safety.
- Clear auditability and compliance.
- Provides a clean foundation for future gated "One-Click Apply" mechanisms once confidence metrics are proven.

---

### ADR-007: Security, Privacy & Telemetry Masking Architecture

#### Context & Problem
Application logs often inadvertently contain Personally Identifiable Information (PII), session tokens, authorization headers, or database connection strings. Feeding unredacted logs into LLMs can violate data privacy standards (GDPR, HIPAA, SOC 2).

#### Decision
Implement a three-tier security architecture:
1. **Pre-Ingestion Sanitization:** High-speed regex masking filters scrub Authorization headers, JWT tokens, API keys, email addresses, credit card formats, and IP addresses before telemetry is stored or sent to Gemini.
2. **Least-Privilege IAM Roles:** The AERO Cloud Run service account is granted read-only telemetry permissions (`roles/logging.viewer`, `roles/monitoring.viewer`, `roles/storage.objectViewer`) and Vertex AI invocation (`roles/aiplatform.user`). It has no compute admin or cluster admin privileges.
3. **Data Boundary Enforcement:** All model invocations and data storage remain strictly within the user's Google Cloud project region.

#### Consequences & Benefits
- Guarantees enterprise-grade data privacy and zero credential leakage.
- Simplifies compliance review for production deployments.

---

### ADR-008: Cost-Conscious Design & Token Budgeting Strategy

#### Context & Problem
Processing large-scale telemetry through advanced LLMs can rapidly exhaust hackathon and operational budgets if not strictly managed.

#### Decision
1. **Window Slicing & Pre-Filtering:** Limit telemetry ingestion to the critical window ($T_{-15\text{min}}$ to $T_{+5\text{min}}$ around incident trigger).
2. **Log Deduplication & Clustering:** Aggregate repetitive error stack traces into frequency histograms (e.g., "500 occurrences of ConnectionTimeoutException in 2 minutes") rather than sending 500 identical raw log lines.
3. **Embedding Caching:** Pre-compute and cache vector embeddings for all static runbooks in Vertex AI Vector Search to avoid re-embedding on every query.
4. **Tiered Model Routing:** Use lightweight fast model tier (`AERO_FAST_MODEL`) for telemetry summarization and filter passes; reserve high-capability reasoning tier (`AERO_REASONING_MODEL`) for final causal synthesis.
5. **Scale-to-Zero Serverless:** Cloud Run containers scale to zero when not actively serving requests.

#### Projected Operational Cost (Demo & Benchmark Tier):
- Cloud Run: $< \$5.00 / \text{month}$ (Scale-to-zero)
- BigQuery & Cloud Storage: $< \$2.00 / \text{month}$
- Vertex AI Gemini Invocations: $< \$10.00$ for full benchmark test suite (100+ diagnostic runs)
- Total Monthly Footprint: Well within standard Google Cloud free/hackathon credits.

---

### ADR-009: AI Evaluation, Ground-Truth Validation & Hallucination Guardrails

#### Context & Problem
To ensure AERO is production-grade, we must measure its diagnostic accuracy and guarantee that it does not hallucinate false root causes or non-existent telemetry.

#### Decision
Establish a formalized **Evaluation Framework** based on three pillars:

1. **Ground-Truth Benchmark Scoring:**
   - Run AERO against the 5 synthetic scenarios.
   - Measure **Root Cause Accuracy (RCA Precision/Recall):** Did AERO identify the exact underlying trigger? (Target: $\ge 85\%$).
2. **Strict Grounding Citation Verification:**
   - Every claim in the diagnostic report must cite a verified timestamp and log/metric ID.
   - Claims lacking a matching citation in the ingested telemetry payload are flagged as hallucinations. (Target: $<2\%$ hallucination rate).
3. **Evaluation Matrix:**

| Metric | Definition | Target |
| :--- | :--- | :--- |
| **Root Cause Accuracy (RCA)** | Correct primary trigger identified vs. ground truth | $\ge 85\%$ |
| **Evidence Completeness** | Percentage of true contributing signals cited | $\ge 90\%$ |
| **Citation Hallucination Rate** | Assertions without valid telemetry backing | $\le 2\%$ |
| **End-to-End Diagnostic Latency** | Time from incident ingest to structured report | $\le 10\text{ seconds}$ |
| **Postmortem Generation Time** | Time to synthesize complete postmortem draft | $\le 15\text{ seconds}$ |
| **Runbook Retrieval Relevance** | Correct runbook retrieved in top-2 results | $\ge 90\%$ |

#### Consequences & Benefits
- Provides rigorous, quantitative proof of AERO’s reliability for the Google Patchamomma evaluation committee.
- Creates an automated regression test suite for future model and prompt enhancements.

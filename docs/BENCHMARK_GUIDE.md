# AERO Synthetic Incident Benchmark Guide

**System:** AERO (AI-Enabled Reliability & Operations)  
**Program:** Google Patchamomma 2026  
**Document Type:** Evaluation & Benchmark Guide  

---

## 1. Overview

The **AERO Synthetic Incident Benchmark Suite** provides a deterministic, reproducible framework for evaluating the diagnostic accuracy, evidence grounding, and causal reasoning capabilities of AI-powered cloud reliability copilots.

To objectively evaluate whether an AI model correctly diagnoses an incident, we need **known, mathematically defined ground truth**. Real enterprise logs are often noisy, proprietary, lack ground-truth causal graphs, and contain private customer data. The synthetic benchmark solves this by generating correlated multi-signal telemetry (application logs, time-series metrics, deployment diffs, and health checks) alongside explicit ground-truth evaluation rules.

---

## 2. The 5 Benchmark Scenarios

| Scenario ID | Scenario Name | Category | Affected Service | Trigger Event | Primary Signal Progression |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`BENCHMARK-OOM-001`** | **Worker Service Memory Leak & Container OOMKill** | `RESOURCE_EXHAUSTION_MEMORY` | `worker-service` | Ingestion of 850MB uncompressed batch payload | Memory utilization ramps $32\% \rightarrow 100\%$, FullGC pauses spike, kernel kills pod (`ExitCode 137`), gateway returns 502s. |
| **`BENCHMARK-DB-002`** | **Order Service Database Connection Pool Starvation** | `DATABASE_CONNECTION_EXHAUSTION` | `order-service` | Deployment of `order-service:v2.4.1` with unindexed query | Active DB connections hit $20/20$ ($100\%$ limit), `HikariPool` connection acquisition times out (30s), checkout returns 504s. |
| **`BENCHMARK-CFG-003`** | **Auth Service Configuration Drift & JWKS URL Mismatch** | `CONFIGURATION_DRIFT` | `auth-service` | ConfigMap update deploying revision `rev-42` | JWKS endpoint DNS lookup fails (`UnknownHostException`), token signature verification collapses, global 401 Unauthorized spike ($98\%$). |
| **`BENCHMARK-DEP-004`** | **Checkout Service Thread Pool Starvation via Upstream Dependency Latency** | `DEPENDENCY_OUTAGE_TIMEOUT` | `checkout-service` | Upstream payment gateway latency spikes to $>28\text{s}$ | Missing client socket timeout; all 100 worker threads block in `WAITING` state, CPU drops to $0\%$, health checks `/healthz` fail. |
| **`BENCHMARK-CACHE-005`** | **Catalog Service Cache Stampede / Cache Key Corruption** | `CACHE_STAMPEDE_SERIALIZATION` | `catalog-service` | Deployment of `catalog-service:v3.1.0` with altered binary serializer | Deserialization errors (`SerializationError`), Redis hit ratio collapses ($98\% \rightarrow 1.8\%$), cache stampede saturates DB CPU at $100\%$. |

---

## 3. CLI Usage & Commands

The benchmark generator CLI is located in `src/benchmark/runner.py`.

### 3.1 List All Available Scenarios
```powershell
python -m src.benchmark.runner --list
```
**Output:**
```
Available AERO Synthetic Benchmark Scenarios:
-------------------------------------------------------------------------------------
* oom_kill               | BENCHMARK-OOM-001    | worker-service   | RESOURCE_EXHAUSTION_MEMORY
* db_pool_exhaustion     | BENCHMARK-DB-002     | order-service    | DATABASE_CONNECTION_EXHAUSTION
* config_drift           | BENCHMARK-CFG-003    | auth-service     | CONFIGURATION_DRIFT
* dependency_deadlock    | BENCHMARK-DEP-004    | checkout-service | DEPENDENCY_OUTAGE_TIMEOUT
* cache_poisoning        | BENCHMARK-CACHE-005  | catalog-service  | CACHE_STAMPEDE_SERIALIZATION
-------------------------------------------------------------------------------------
```

### 3.2 Inspect Scenario Ground Truth & Telemetry Structure
```powershell
python -m src.benchmark.runner --inspect db_pool_exhaustion
```
Displays:
- Affected microservice & taxonomy category
- Exact ground-truth root-cause summary
- List of mandatory evidence patterns (logs, metrics, deployments) required for high grounding scores
- Expected remediation checklist
- Telemetry signal breakdown (counts of logs, metrics, deployments, health checks)

### 3.3 Generate Benchmark Datasets to Disk
```powershell
# Generate all 5 scenarios with default seed (42) to data/benchmark/ in JSON and JSONL formats
python -m src.benchmark.runner --generate

# Custom seed and destination directory
python -m src.benchmark.runner --generate --output-dir data/my_custom_benchmark --seed 999 --format both
```

---

## 4. Dataset File Layout & Formats

When generated, the datasets are stored in `data/benchmark/`:

```
data/benchmark/
├── manifest.json              # Index of all scenarios with file paths and metadata
├── oom_kill.json              # Full nested BenchmarkScenarioBundle
├── oom_kill.jsonl             # Line 1: GroundTruthScenario, Line 2: Incident Telemetry
├── db_pool_exhaustion.json
├── db_pool_exhaustion.jsonl
├── config_drift.json
├── config_drift.jsonl
├── dependency_deadlock.json
├── dependency_deadlock.jsonl
├── cache_poisoning.json
└── cache_poisoning.jsonl
```

### Bundle JSON Schema Structure
Each scenario `.json` file contains:
```json
{
  "ground_truth": {
    "scenario_id": "BENCHMARK-DB-002",
    "scenario_name": "Order Service Database Connection Pool Starvation",
    "category": "DATABASE_CONNECTION_EXHAUSTION",
    "affected_service": "order-service",
    "trigger_event": "Deployment of order-service:v2.4.1 containing an unindexed query in checkout workflow.",
    "root_cause_summary": "Release v2.4.1 introduced a slow unindexed database query...",
    "expected_root_cause_category": "DATABASE_CONNECTION_EXHAUSTION",
    "expected_evidence_signals": [
      {
        "signal_type": "DEPLOYMENT",
        "pattern": "v2.4.1",
        "description": "Deployment event of order-service:v2.4.1 preceding pool saturation.",
        "is_mandatory": true
      }
    ],
    "expected_remediation": {
      "key_actions": ["Rollback order-service to v2.4.0", "Add database index", "Increase pool size"],
      "expected_verification_metric": "database/pool/active_connections drops below 10"
    }
  },
  "incident": {
    "metadata": {
      "incident_id": "INC-20260830-DB",
      "title": "Order Service 504 Outage: DB Connection Pool Exhaustion",
      "severity": "SEV1_CRITICAL",
      "status": "INVESTIGATING",
      "affected_service": "order-service",
      "detected_at": "2026-08-30T14:08:00Z"
    },
    "telemetry": {
      "time_window_start": "2026-08-30T14:00:00Z",
      "time_window_end": "2026-08-30T14:25:00Z",
      "logs": [...],
      "metrics": [...],
      "deployments": [...],
      "health_signals": [...]
    }
  }
}
```

---

## 5. Quantitative AI Evaluation Methodology

When evaluating an AI diagnostic engine (such as Gemini in subsequent implementation steps), the system computes three objective metrics against ground truth:

1. **Root Cause Identification Accuracy (RCA Score, 0–1):**
   - Exact category match (`expected_root_cause_category`) + semantic similarity to `root_cause_summary`.
   - Benchmark target: $\ge 85\%$.

2. **Evidence Grounding Precision & Recall (0–1):**
   - **Evidence Recall:** Did the AI cite all mandatory evidence signals defined in `expected_evidence_signals`?
   - **Evidence Precision / Hallucination Guardrail:** Did the AI cite non-existent timestamps or fabricate metric values?
   - Benchmark target: Recall $\ge 90\%$, Hallucination rate $\le 2\%$.

3. **Remediation Plan Completeness (0–1):**
   - Does the suggested remediation contain the necessary rollback/mitigation steps and recovery verification metric?
   - Benchmark target: $\ge 80\%$.

---

## 6. Running the Test Suite

Run pytest to verify schema validation, deterministic generator reproducibility, and scenario ground-truth integrity:

```powershell
python -m pytest -v
```
All 19 tests should pass with 100% success.

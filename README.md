# AERO: AI-Enabled Reliability & Operations

> **Next-generation incident intelligence copilot that helps engineering teams understand, resolve, learn from, and prevent production outages in cloud-native applications.**

[![Cloud Run Status](https://img.shields.io/badge/Deployment-Cloud%20Run%20Live-success?logo=googlecloud&logoColor=white)](https://aero-723610618470.us-central1.run.app/)
[![AI Foundation](https://img.shields.io/badge/Vertex%20AI-Gemini%202.5%20Pro%20%26%20Flash-4285F4?logo=google)](https://cloud.google.com/vertex-ai)
[![Backend](https://img.shields.io/badge/Backend-Python%203.12%20%7C%20FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Test Suite](https://img.shields.io/badge/Tests-164%20Passing-brightgreen?logo=pytest&logoColor=white)](https://github.com/nishanki-singh/aero-project)
[![Documentation](https://img.shields.io/badge/Submission%20Dossier-Google%20Doc-blue?logo=googledocs&logoColor=white)](https://docs.google.com/document/d/1Oa270l4n-wk86AJHZiWh2hPhKem-br9YSSHTmqeAx6s/edit?tab=t.0)

---

## Quick Links & Live Artifacts

| Resource | Link | Description |
| :--- | :--- | :--- |
| **Live Web Application** | [aero-723610618470.us-central1.run.app](https://aero-723610618470.us-central1.run.app/) | Deployed on Google Cloud Run with live Vertex AI inference |
| **Submission & Tech Doc** | [Google Docs Full Technical Dossier](https://docs.google.com/document/d/1Oa270l4n-wk86AJHZiWh2hPhKem-br9YSSHTmqeAx6s/edit?tab=t.0) | Complete architecture, verification, and evaluation report |
| **Source Repository** | [github.com/nishanki-singh/aero-project](https://github.com/nishanki-singh/aero-project) | Open-source implementation with 164 automated tests |

---

## What is AERO?

During critical production incidents, on-call engineers drown in thousands of disparate logs, metrics, and alerts. Generic LLMs exacerbate the problem by hallucinating plausible-sounding fixes.

**AERO bridges the gap between raw telemetry and actionable resolution through evidence-grounded AI:**
- **Zero-Guesswork RCA:** Evaluates telemetry against deterministic causal graphs and strictly validates AI-generated hypotheses against observed telemetry.
- **Dual-Model Tiering:** Routes high-speed chat and triage to **Gemini 2.5 Flash**, while reserving **Gemini 2.5 Pro** for deep root-cause synthesis and postmortem generation.
- **Deterministic Reliability:** Backed by 164 automated unit & integration tests, ensuring production stability without brittle mocks.

---

## Architecture Pillars

| Pillar | Focus | Capability |
| :--- | :--- | :--- |
| **🔍 Understand** | Triage & Blast Radius | Ingests alerts, reconstructs unified timelines, and computes service dependency impact graphs. |
| **🧠 Remember** | Historical Pattern Matching | Correlates recurring operational failures with past incidents and organizational runbooks. |
| **📝 Document** | Automated Postmortems | Synthesizes verified evidence into comprehensive, blameless post-incident reviews in seconds. |
| **🛡️ Prevent** | Proactive Risk Analysis | Scores proposed PRs and config changes against historical failure modes before they reach production. |

---

## Highlights

1. **Live Cloud Run Validation**:
   - **Revision:** `aero-00001-csm`
   - **Region:** `us-central1`
   - Real-time interaction with Google Cloud Vertex AI APIs in a fully containerized serverless environment.

2. **Grounding & Verifiable Claims**:
   - Every AI insight is coupled with deterministic citation verification—separating *observed facts* from *inferred reasoning* to eliminate hallucinated operations advice.

3. **Production-Ready Python 3.12 / FastAPI Stack**:
   - Asynchronous endpoints, strict Pydantic v2 schemas, and robust retry logic via Tenacity for resilient upstream AI calls.

---

## Quick Local Setup

```bash
# Clone the repository
git clone https://github.com/nishanki-singh/aero-project.git
cd aero-project

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Or: .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run the test suite (164 tests)
pytest -v

# Start local server
uvicorn src.api.main:app --reload --port 8000

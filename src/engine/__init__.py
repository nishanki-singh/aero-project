"""Engine package for AERO telemetry correlation and AI diagnostics."""

from src.engine.correlator import (
    CorrelatedTelemetrySummary,
    ErrorLogCluster,
    MetricAnomaly,
    TelemetryCorrelator,
)
from src.engine.diagnostic_engine import (
    BaseDiagnosticEngine,
    MockDiagnosticEngine,
    VertexAiDiagnosticEngine,
    get_diagnostic_engine,
)
from src.engine.grounding_verifier import (
    GroundedEvidenceItem,
    GroundingVerificationResult,
    GroundingVerifier,
)
from src.engine.prompts import SYSTEM_INSTRUCTION, build_diagnostic_prompt

__all__ = [
    "ErrorLogCluster",
    "MetricAnomaly",
    "CorrelatedTelemetrySummary",
    "TelemetryCorrelator",
    "SYSTEM_INSTRUCTION",
    "build_diagnostic_prompt",
    "GroundedEvidenceItem",
    "GroundingVerificationResult",
    "GroundingVerifier",
    "BaseDiagnosticEngine",
    "MockDiagnosticEngine",
    "VertexAiDiagnosticEngine",
    "get_diagnostic_engine",
]

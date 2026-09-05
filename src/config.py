"""Configuration module for AERO.

Centralizes environment variables, model tier parameters, and benchmark defaults.
All models are fully configurable via environment variables without hardcoded legacy fallbacks.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class AeroConfig(BaseModel):
    """Configuration container for AERO services."""

    # Google Cloud Project & Region
    project_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "project-a47199cc-a109-4cd5-917"),
        description="Google Cloud Project ID for Vertex AI and cloud services.",
    )
    region: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_REGION", "us-central1"),
        description="Google Cloud Region for Vertex AI model endpoints.",
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("AERO_ENV", "development"),
        description="Runtime environment (development, staging, production).",
    )

    # Configurable Model Tiers (Current Generation Defaults)
    reasoning_model: str = Field(
        default_factory=lambda: os.getenv("AERO_REASONING_MODEL", "gemini-2.5-pro"),
        description="High-capability Gemini model for causal root-cause reasoning and postmortems.",
    )
    fast_model: str = Field(
        default_factory=lambda: os.getenv("AERO_FAST_MODEL", "gemini-2.5-flash"),
        description="Low-latency Gemini model for telemetry pre-filtering, anomaly extraction, and chat.",
    )
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("AERO_EMBEDDING_MODEL", "text-embedding-005"),
        description="Vertex AI embedding model for Engineering Memory vector search.",
    )

    # Engine Provider Mode ("auto", "vertex", "mock")
    diagnostic_provider: str = Field(
        default_factory=lambda: os.getenv("AERO_DIAGNOSTIC_PROVIDER", "auto"),
        description="Default diagnostic provider: 'auto', 'vertex', or 'mock'.",
    )

    # Benchmark & Evaluation Paths
    benchmark_data_dir: str = Field(
        default_factory=lambda: os.getenv("AERO_BENCHMARK_DATA_DIR", "data/benchmark"),
        description="Directory to store generated reproducible benchmark incident datasets.",
    )
    default_random_seed: int = Field(
        default=42,
        description="Default random seed for deterministic benchmark generation.",
    )


# Global singleton instance
config = AeroConfig()

"""Configuration module for AERO.

Centralizes environment variables, model tier parameters, and benchmark defaults.
"""

from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field


class AeroConfig(BaseModel):
    """Configuration container for AERO services."""

    # Project metadata
    project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "aero-demo-project"))
    region: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_REGION", "us-central1"))
    environment: str = Field(default_factory=lambda: os.getenv("AERO_ENV", "development"))

    # Configurable Model Tiers
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

    # Benchmark & Data Paths
    benchmark_data_dir: str = Field(
        default_factory=lambda: os.getenv("AERO_BENCHMARK_DATA_DIR", "data/benchmark"),
        description="Directory to store generated reproducible benchmark incident datasets.",
    )
    default_random_seed: int = Field(default=42, description="Default seed for deterministic benchmark generation.")


# Global singleton instance
config = AeroConfig()

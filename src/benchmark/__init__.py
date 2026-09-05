"""Benchmark package for AERO synthetic incident evaluation."""

from src.benchmark.generator import SyntheticIncidentGenerator
from src.benchmark.scenarios import (
    BENCHMARK_SCENARIOS,
    generate_cache_poisoning_scenario,
    generate_config_drift_scenario,
    generate_db_pool_exhaustion_scenario,
    generate_dependency_deadlock_scenario,
    generate_oom_kill_scenario,
)

__all__ = [
    "BENCHMARK_SCENARIOS",
    "SyntheticIncidentGenerator",
    "generate_cache_poisoning_scenario",
    "generate_config_drift_scenario",
    "generate_db_pool_exhaustion_scenario",
    "generate_dependency_deadlock_scenario",
    "generate_oom_kill_scenario",
]

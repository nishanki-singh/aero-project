"""Benchmark scenarios registry and loaders."""

from collections.abc import Callable

from src.benchmark.scenarios.cache_poisoning import generate_cache_poisoning_scenario
from src.benchmark.scenarios.config_drift import generate_config_drift_scenario
from src.benchmark.scenarios.db_pool_exhaustion import (
    generate_db_pool_exhaustion_scenario,
)
from src.benchmark.scenarios.dependency_deadlock import (
    generate_dependency_deadlock_scenario,
)
from src.benchmark.scenarios.oom_kill import generate_oom_kill_scenario
from src.schemas.ground_truth import BenchmarkScenarioBundle

BENCHMARK_SCENARIOS: dict[str, Callable[..., BenchmarkScenarioBundle]] = {
    "oom_kill": generate_oom_kill_scenario,
    "db_pool_exhaustion": generate_db_pool_exhaustion_scenario,
    "config_drift": generate_config_drift_scenario,
    "dependency_deadlock": generate_dependency_deadlock_scenario,
    "cache_poisoning": generate_cache_poisoning_scenario,
}

__all__ = [
    "BENCHMARK_SCENARIOS",
    "generate_cache_poisoning_scenario",
    "generate_config_drift_scenario",
    "generate_db_pool_exhaustion_scenario",
    "generate_dependency_deadlock_scenario",
    "generate_oom_kill_scenario",
]

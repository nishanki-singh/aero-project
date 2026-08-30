"""Synthetic telemetry and incident generation engine for reproducible benchmarking."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from src.schemas.telemetry import (
    DeploymentEvent,
    HealthStatus,
    LogEntry,
    LogLevel,
    MetricPoint,
    MetricSeries,
    ServiceHealth,
)


class SyntheticIncidentGenerator:
    """Engine for generating correlated multi-signal telemetry with deterministic seeds and background noise."""

    def __init__(self, seed: int = 42, base_time: Optional[datetime] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base_time = base_time or datetime(2026, 8, 30, 14, 0, 0, tzinfo=timezone.utc)

    def generate_background_logs(
        self,
        services: List[str],
        start_time: datetime,
        duration_minutes: int = 25,
        logs_per_minute: int = 2,
    ) -> List[LogEntry]:
        """Generates realistic healthy background INFO/DEBUG logs across microservices."""
        sample_messages = [
            "Processed HTTP GET /healthz 200 OK in 2.1ms",
            "Dispatched background async notification to queue",
            "Refreshed security token cache successfully",
            "Processed order batch item from Kafka topic",
            "Executed periodic garbage collection cycle",
            "Retrieved cached user session from memory",
        ]
        logs: List[LogEntry] = []
        for minute in range(duration_minutes):
            current_time = start_time + timedelta(minutes=minute)
            for svc in services:
                for _ in range(logs_per_minute):
                    offset_sec = self.rng.randint(0, 59)
                    msg_time = current_time + timedelta(seconds=offset_sec)
                    msg = self.rng.choice(sample_messages)
                    logs.append(
                        LogEntry(
                            timestamp=msg_time,
                            service_name=svc,
                            log_level=LogLevel.INFO,
                            message=msg,
                            trace_id=f"trace-{self.rng.randint(100000, 999999)}",
                            attributes={"environment": "production", "region": "us-central1"},
                        )
                    )
        return logs

    def generate_baseline_metrics(
        self,
        service_name: str,
        metric_name: str,
        unit: str,
        start_time: datetime,
        duration_minutes: int = 25,
        base_value: float = 20.0,
        jitter: float = 3.0,
    ) -> MetricSeries:
        """Generates healthy baseline metric time-series with small random jitter."""
        points: List[MetricPoint] = []
        for minute in range(duration_minutes):
            t = start_time + timedelta(minutes=minute)
            val = max(0.0, base_value + self.rng.uniform(-jitter, jitter))
            points.append(MetricPoint(timestamp=t, value=round(val, 2)))
        return MetricSeries(
            metric_name=metric_name,
            service_name=service_name,
            unit=unit,
            points=points,
            labels={"tier": "backend", "service": service_name},
        )

    def generate_baseline_health(
        self,
        services: List[str],
        start_time: datetime,
        duration_minutes: int = 25,
    ) -> List[ServiceHealth]:
        """Generates healthy baseline ServiceHealth records every 2 minutes."""
        health_records: List[ServiceHealth] = []
        for minute in range(0, duration_minutes, 2):
            t = start_time + timedelta(minutes=minute)
            for svc in services:
                health_records.append(
                    ServiceHealth(
                        timestamp=t,
                        service_name=svc,
                        status=HealthStatus.HEALTHY,
                        latency_p99_ms=round(self.rng.uniform(15.0, 35.0), 2),
                        error_rate_pct=round(self.rng.uniform(0.0, 0.05), 3),
                        details="All health checks passing (200 OK)",
                    )
                )
        return health_records

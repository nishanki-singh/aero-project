"""Deterministic grounding verifier for SRE Copilot responses."""

from __future__ import annotations

from src.schemas.chat import ChatResponse, EvidenceItem
from src.schemas.diagnostic import SignalType
from src.schemas.incident import Incident


class CopilotGroundingVerifier:
    """Validates that cited Observed Evidence in Copilot responses exists in active telemetry."""

    @classmethod
    def verify(cls, response: ChatResponse, incident: Incident) -> tuple[bool, list[str]]:
        """Validates all evidence items against active incident telemetry.
        
        Returns:
            tuple: (is_grounded, list_of_failed_claims)
        """
        failed_claims: list[str] = []
        telemetry = incident.telemetry

        # Index active telemetry signals
        metric_names = {m.metric_name for m in telemetry.metrics}
        all_logs = [l.message.lower() for l in telemetry.logs]
        deployments = telemetry.deployments

        for idx, item in enumerate(response.evidence):
            is_item_grounded = cls._verify_item(item, metric_names, all_logs, deployments, incident)
            if not is_item_grounded:
                failed_claims.append(
                    f"Evidence item #{idx + 1} ({item.signal_type.value}: '{item.description}') "
                    f"could not be substantiated in active telemetry."
                )

        is_grounded = len(failed_claims) == 0
        return is_grounded, failed_claims

    @classmethod
    def _verify_item(
        cls,
        item: EvidenceItem,
        metric_names: set[str],
        all_logs: list[str],
        deployments: list,
        incident: Incident,
    ) -> bool:
        """Verifies a single evidence item."""
        if item.signal_type == SignalType.METRIC:
            # Must reference an actual metric series in the incident
            if item.metric_name and item.metric_name in metric_names:
                return True
            # Or item.source must be a valid metric name
            if item.source in metric_names:
                return True
            # Check if any active metric name is contained in the description
            return any(name in item.description for name in metric_names)

        elif item.signal_type == SignalType.LOG:
            # Check if log snippet or description matches any log line
            query = (item.log_snippet or item.description).lower()
            if any(query in log for log in all_logs):
                return True
            tokens = [t for t in query.split() if len(t) > 4 and t.isalnum()]
            return bool(tokens and any(all(t in log for t in tokens[:3]) for log in all_logs))

        elif item.signal_type == SignalType.DEPLOYMENT:
            # If telemetry has deployments, check if service/version matches
            if deployments:
                for d in deployments:
                    if d.service_name.lower() in item.description.lower() or d.version.lower() in item.description.lower():
                        return True
                    if d.commit_hash.lower() in item.description.lower():
                        return True
                return False
            else:
                # If no deployments exist, the evidence should explicitly state no deployments
                desc = item.description.lower()
                return "no deployment" in desc or "0 deployment" in desc or "zero deployment" in desc

        elif item.signal_type == SignalType.HEALTH:
            # Check service health signals
            health_statuses = {h.status.value.lower() for h in incident.telemetry.health_signals}
            desc = item.description.lower()
            return any(status in desc for status in health_statuses) or incident.metadata.affected_service.lower() in desc

        return False

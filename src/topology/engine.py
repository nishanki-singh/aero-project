"""Deterministic graph traversal and dynamic blast-radius calculation engine."""

from __future__ import annotations

from collections import deque

from src.schemas.topology import (
    BlastRadiusReport,
    CriticalPathImpact,
    TopologyGraph,
)
from src.topology.graph import build_canonical_topology_graph

CRITICAL_SERVICES = {"checkout-service", "order-service", "payment-service", "api-gateway", "auth-service"}


class BlastRadiusEngine:
    """Graph traversal and blast-radius evaluation engine."""

    def __init__(self, graph: TopologyGraph | None = None) -> None:
        self.graph = graph or build_canonical_topology_graph()
        self._build_adjacency()

    def _build_adjacency(self) -> None:
        """Constructs forward and reverse adjacency lists."""
        self.forward_adj: dict[str, list[str]] = {node.id: [] for node in self.graph.nodes}
        self.reverse_adj: dict[str, list[str]] = {node.id: [] for node in self.graph.nodes}

        for edge in self.graph.edges:
            if edge.source in self.forward_adj and edge.target in self.forward_adj:
                self.forward_adj[edge.source].append(edge.target)
                self.reverse_adj[edge.target].append(edge.source)

    def find_cascade_paths(self, start_node: str, max_depth: int = 6) -> list[list[str]]:
        """Finds all upstream failure propagation paths from target up to ingress or top callers."""
        paths: list[list[str]] = []

        def dfs(current: str, current_path: list[str]) -> None:
            upstreams = self.reverse_adj.get(current, [])
            # Filter out cycles in current path
            valid_upstreams = [u for u in upstreams if u not in current_path]

            if not valid_upstreams or len(current_path) >= max_depth or current == "api-gateway":
                paths.append(list(current_path))
                return

            for upstream in valid_upstreams:
                current_path.append(upstream)
                dfs(upstream, current_path)
                current_path.pop()

        dfs(start_node, [start_node])
        return paths

    def compute_blast_radius(
        self,
        target_service: str,
        impacted_nodes_override: list[str] | set[str] | None = None,
    ) -> BlastRadiusReport:
        """Dynamically computes the upstream blast-radius for a given target service/datastore."""
        if target_service not in self.forward_adj:
            # Service not in graph, return minimal report
            total_nodes = len(self.graph.nodes) or 11
            return BlastRadiusReport(
                target_service=target_service,
                direct_upstream=[],
                transitive_upstream=[],
                direct_downstream=[],
                total_impacted_services=1,
                total_nodes_in_system=total_nodes,
                blast_radius_pct=round((1 / total_nodes) * 100.0, 1),
                impact_level="ISOLATED",
                critical_path_breached=False,
                cascade_paths=[[target_service]],
                critical_path_impact=CriticalPathImpact.NONE,
            )

        direct_downstream = list(self.forward_adj.get(target_service, []))
        direct_upstream = list(self.reverse_adj.get(target_service, []))

        # BFS for all reachable upstream callers
        visited_upstream: set[str] = set()
        queue: deque[str] = deque(direct_upstream)
        for u in direct_upstream:
            visited_upstream.add(u)

        while queue:
            curr = queue.popleft()
            for parent in self.reverse_adj.get(curr, []):
                if parent not in visited_upstream and parent != target_service:
                    visited_upstream.add(parent)
                    queue.append(parent)

        transitive_upstream = [u for u in visited_upstream if u not in direct_upstream]

        # Total impacted includes target itself, all upstreams, and any active failure cascade nodes
        total_impacted_set = set(direct_upstream) | set(transitive_upstream) | {target_service}
        if impacted_nodes_override:
            total_impacted_set.update(impacted_nodes_override)

        total_impacted_count = len(total_impacted_set)
        total_nodes = len(self.graph.nodes) or 11

        # Dynamic computation
        blast_radius_pct = round((total_impacted_count / total_nodes) * 100.0, 1)


        # Critical path detection
        critical_intersect = total_impacted_set.intersection(CRITICAL_SERVICES)
        critical_path_breached = len(critical_intersect) >= 2 or (
            "checkout-service" in total_impacted_set or "payment-service" in total_impacted_set
        )

        # Impact level & qualitative critical path impact
        if blast_radius_pct >= 60.0:
            impact_level = "CATASTROPHIC"
            critical_impact = CriticalPathImpact.CRITICAL
        elif blast_radius_pct >= 40.0:
            impact_level = "HIGH"
            critical_impact = CriticalPathImpact.HIGH if critical_path_breached else CriticalPathImpact.MODERATE
        elif blast_radius_pct >= 20.0:
            impact_level = "MODERATE"
            critical_impact = CriticalPathImpact.MODERATE if critical_path_breached else CriticalPathImpact.LOW
        else:
            impact_level = "ISOLATED"
            critical_impact = CriticalPathImpact.LOW if critical_path_breached else CriticalPathImpact.NONE

        cascade_paths = self.find_cascade_paths(target_service)

        return BlastRadiusReport(
            target_service=target_service,
            direct_upstream=sorted(direct_upstream),
            transitive_upstream=sorted(transitive_upstream),
            direct_downstream=sorted(direct_downstream),
            total_impacted_services=total_impacted_count,
            total_nodes_in_system=total_nodes,
            blast_radius_pct=blast_radius_pct,
            impact_level=impact_level,
            critical_path_breached=critical_path_breached,
            cascade_paths=cascade_paths,
            critical_path_impact=critical_impact,
        )


def evaluate_blast_radius(
    target_service: str,
    graph: TopologyGraph | None = None,
) -> BlastRadiusReport:
    """Convenience helper to compute blast radius on a topology graph."""
    engine = BlastRadiusEngine(graph=graph)
    return engine.compute_blast_radius(target_service=target_service)

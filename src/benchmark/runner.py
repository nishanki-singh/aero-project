"""Benchmark runner CLI for generating, inspecting, and exporting synthetic incident datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.benchmark.scenarios import BENCHMARK_SCENARIOS
from src.config import config


def export_benchmark_datasets(
    output_dir: str | None = None,
    seed: int = 42,
    export_format: str = "both",
) -> None:
    """Generates and exports all 5 benchmark scenarios to disk."""
    out_path = Path(output_dir or config.benchmark_data_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"\n[AERO] Generating Synthetic Benchmark Scenarios (seed={seed})...")
    print(f"[AERO] Destination directory: {out_path.resolve()}\n")

    manifest = []

    for name, generator_fn in BENCHMARK_SCENARIOS.items():
        bundle = generator_fn(seed=seed)
        scenario_id = bundle.ground_truth.scenario_id
        svc = bundle.ground_truth.affected_service
        cat = bundle.ground_truth.category

        # JSON Export (Full Bundle)
        if export_format in ("json", "both"):
            json_file = out_path / f"{name}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                f.write(bundle.model_dump_json(indent=2))

        # JSONL Export (Separate Incident Telemetry from Ground Truth)
        if export_format in ("jsonl", "both"):
            jsonl_file = out_path / f"{name}.jsonl"
            with open(jsonl_file, "w", encoding="utf-8") as f:
                # Line 1: Ground Truth
                f.write(bundle.ground_truth.model_dump_json() + "\n")
                # Line 2: Incident Metadata & Telemetry
                f.write(bundle.incident.model_dump_json() + "\n")

        log_count = len(bundle.incident.telemetry.logs)
        metric_count = len(bundle.incident.telemetry.metrics)
        deploy_count = len(bundle.incident.telemetry.deployments)
        health_count = len(bundle.incident.telemetry.health_signals)

        print(f"  [OK] [{scenario_id}] {bundle.ground_truth.scenario_name}")
        print(f"       Service: {svc} | Category: {cat}")
        print(f"       Telemetry: {log_count} logs, {metric_count} metrics, {deploy_count} deploys, {health_count} health checks")

        manifest.append(
            {
                "scenario_id": scenario_id,
                "name": name,
                "title": bundle.ground_truth.scenario_name,
                "category": cat,
                "service": svc,
                "files": {
                    "json": f"{name}.json" if export_format in ("json", "both") else None,
                    "jsonl": f"{name}.jsonl" if export_format in ("jsonl", "both") else None,
                },
            }
        )

    manifest_file = out_path / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "total_scenarios": len(manifest), "scenarios": manifest}, f, indent=2)

    print(f"\n[DONE] Generated {len(manifest)} benchmark scenarios successfully. Manifest saved to {manifest_file}\n")


def inspect_scenario(name: str, seed: int = 42) -> None:
    """Inspects and displays details of a specific benchmark scenario."""
    if name not in BENCHMARK_SCENARIOS:
        print(f"[ERROR] Unknown scenario '{name}'. Available scenarios: {list(BENCHMARK_SCENARIOS.keys())}")
        sys.exit(1)

    bundle = BENCHMARK_SCENARIOS[name](seed=seed)
    gt = bundle.ground_truth
    inc = bundle.incident

    print("\n" + "=" * 80)
    print(f"SCENARIO: {gt.scenario_name} ({gt.scenario_id})")
    print("=" * 80)
    print(f"- Affected Service:       {gt.affected_service}")
    print(f"- Category:               {gt.category}")
    print(f"- Incident Title:         {inc.metadata.title}")
    print(f"- Severity:               {inc.metadata.severity.value}")
    print(f"- Trigger Event:          {gt.trigger_event}")
    print(f"\n- Ground-Truth Root Cause:\n  {gt.root_cause_summary}")
    print(f"\n- Expected Mandatory Evidence Citations ({len(gt.expected_evidence_signals)} signals):")
    for idx, ev in enumerate(gt.expected_evidence_signals, 1):
        mand = "[MANDATORY]" if ev.is_mandatory else "[OPTIONAL]"
        print(f"  {idx}. {mand} [{ev.signal_type.value}] Pattern: '{ev.pattern}'")
        print(f"     Reason: {ev.description}")
    print("\n- Expected Key Remediation Actions:")
    for act in gt.expected_remediation.key_actions:
        print(f"  * {act}")
    print(f"- Recovery Metric: {gt.expected_remediation.expected_verification_metric}")
    print("\n- Telemetry Summary:")
    print(f"  * Logs:           {len(inc.telemetry.logs)} entries")
    print(f"  * Metric Series:  {len(inc.telemetry.metrics)} series")
    print(f"  * Deployments:    {len(inc.telemetry.deployments)} events")
    print(f"  * Health Checks:  {len(inc.telemetry.health_signals)} checks")
    print("=" * 80 + "\n")


def list_scenarios() -> None:
    """Lists all registered benchmark scenarios."""
    print("\nAvailable AERO Synthetic Benchmark Scenarios:")
    print("-" * 85)
    for name, gen_fn in BENCHMARK_SCENARIOS.items():
        bundle = gen_fn(seed=42)
        gt = bundle.ground_truth
        print(f"* {name:<22} | {gt.scenario_id:<20} | {gt.affected_service:<16} | {gt.category}")
    print("-" * 85 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="AERO Synthetic Incident Benchmark CLI")
    parser.add_argument("--generate", action="store_true", help="Generate all benchmark scenario datasets")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save generated datasets")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--format", choices=["json", "jsonl", "both"], default="both", help="Export file format")
    parser.add_argument("--list", action="store_true", help="List all available benchmark scenarios")
    parser.add_argument("--inspect", type=str, default=None, help="Inspect details of a specific scenario")

    args = parser.parse_args()

    if args.list:
        list_scenarios()
    elif args.inspect:
        inspect_scenario(args.inspect, seed=args.seed)
    elif args.generate or len(sys.argv) == 1:
        export_benchmark_datasets(output_dir=args.output_dir, seed=args.seed, export_format=args.format)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

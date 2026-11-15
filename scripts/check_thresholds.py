"""CI Evaluation Threshold Checker (Requirement E2).

Reads evals/results/smoke_latest.json and enforces thresholds defined in
agent/config.yaml under ci_gates.smoke. Exits with 0 on pass, 1 on breach.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RESULTS_FILE = Path(__file__).resolve().parent.parent / "evals" / "results" / "smoke_latest.json"
DEFAULT_CONFIG_FILE = Path(__file__).resolve().parent.parent / "agent" / "config.yaml"


def check_thresholds(
    results_path: Path = DEFAULT_RESULTS_FILE,
    config_path: Path = DEFAULT_CONFIG_FILE,
) -> int:
    """Verifies that smoke evaluation metrics satisfy configured CI gates."""
    if not results_path.is_file():
        print(f"ERROR: Results file not found: {results_path}", file=sys.stderr)
        return 1

    if not config_path.is_file():
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        results: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed parsing results JSON: {exc}", file=sys.stderr)
        return 1

    try:
        config: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed parsing config YAML: {exc}", file=sys.stderr)
        return 1

    ci_gates = config.get("ci_gates", {}).get("smoke", {})
    max_unsupported = float(ci_gates.get("max_unsupported_claim_rate", 0.05))
    min_f1 = float(ci_gates.get("min_bid_or_skip_f1", 0.70))
    min_ndcg = float(ci_gates.get("min_retrieval_ndcg_at_10", 0.35))

    metrics = results.get("metrics", {})
    actual_unsupported = float(metrics.get("unsupported_claim_rate", 0.0))
    actual_f1 = float(metrics.get("bid_or_skip_f1", 0.0))
    actual_ndcg = float(metrics.get("retrieval_ndcg_at_10", 0.0))

    failures: list[str] = []

    print("================================================================================")
    print("                      CI EVALUATION THRESHOLD GATE (E2)                        ")
    print("================================================================================")
    print(f"{'Metric':<35} | {'Measured':<10} | {'Threshold':<12} | {'Status'}")
    print("--------------------------------------------------------------------------------")

    # 1. Unsupported Claim Rate (lower is better)
    status_unsupported = "PASS" if actual_unsupported <= max_unsupported else "FAIL"
    if status_unsupported == "FAIL":
        failures.append(f"unsupported_claim_rate {actual_unsupported:.4f} > {max_unsupported:.4f}")
    print(f"{'unsupported_claim_rate':<35} | {actual_unsupported:<10.4f} | {f'<= {max_unsupported:.4f}':<12} | {status_unsupported}")

    # 2. Bid or Skip F1 (higher is better)
    status_f1 = "PASS" if actual_f1 >= min_f1 else "FAIL"
    if status_f1 == "FAIL":
        failures.append(f"bid_or_skip_f1 {actual_f1:.4f} < {min_f1:.4f}")
    print(f"{'bid_or_skip_f1':<35} | {actual_f1:<10.4f} | {f'>= {min_f1:.4f}':<12} | {status_f1}")

    # 3. Retrieval nDCG@10 (higher is better)
    status_ndcg = "PASS" if actual_ndcg >= min_ndcg else "FAIL"
    if status_ndcg == "FAIL":
        failures.append(f"retrieval_ndcg_at_10 {actual_ndcg:.4f} < {min_ndcg:.4f}")
    print(f"{'retrieval_ndcg_at_10':<35} | {actual_ndcg:<10.4f} | {f'>= {min_ndcg:.4f}':<12} | {status_ndcg}")
    print("================================================================================")

    if failures:
        print(f"GATE FAILED: {len(failures)} threshold(s) breached:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("GATE PASSED: All CI plumbing integrity thresholds satisfied.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CI smoke evaluation thresholds")
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_FILE)
    parser.add_argument("--config-path", type=Path, default=DEFAULT_CONFIG_FILE)
    args = parser.parse_args()

    sys.exit(check_thresholds(results_path=args.results_path, config_path=args.config_path))


if __name__ == "__main__":
    main()

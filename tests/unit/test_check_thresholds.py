"""Unit test proving the CI Eval Gate fails on a deliberately bad result (Requirement E2)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.check_thresholds import check_thresholds


def test_gate_passes_on_good_result(tmp_path: Path) -> None:
    """Verifies that check_thresholds returns 0 when all metrics satisfy thresholds."""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "ci_gates": {
            "smoke": {
                "max_unsupported_claim_rate": 0.05,
                "min_bid_or_skip_f1": 0.70,
                "min_retrieval_ndcg_at_10": 0.35,
            }
        }
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    results_file = tmp_path / "smoke_latest.json"
    results_data = {
        "metrics": {
            "unsupported_claim_rate": 0.0,
            "bid_or_skip_f1": 0.85,
            "retrieval_ndcg_at_10": 0.50,
        }
    }
    results_file.write_text(json.dumps(results_data), encoding="utf-8")

    exit_code = check_thresholds(results_path=results_file, config_path=config_file)
    assert exit_code == 0


def test_gate_fails_on_deliberately_bad_result(tmp_path: Path) -> None:
    """Proves that check_thresholds exits with code 1 when metrics breach configured gates."""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "ci_gates": {
            "smoke": {
                "max_unsupported_claim_rate": 0.05,
                "min_bid_or_skip_f1": 0.70,
                "min_retrieval_ndcg_at_10": 0.35,
            }
        }
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Deliberately bad results:
    # 1. High unsupported claim rate (0.25 > 0.05)
    # 2. Low F1 (0.40 < 0.70)
    # 3. Low nDCG (0.20 < 0.35)
    bad_results_file = tmp_path / "bad_smoke.json"
    bad_results_data = {
        "metrics": {
            "unsupported_claim_rate": 0.25,
            "bid_or_skip_f1": 0.40,
            "retrieval_ndcg_at_10": 0.20,
        }
    }
    bad_results_file.write_text(json.dumps(bad_results_data), encoding="utf-8")

    exit_code = check_thresholds(results_path=bad_results_file, config_path=config_file)
    assert exit_code == 1

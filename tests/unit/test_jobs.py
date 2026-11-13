"""Unit tests for job data preparation and adversarial injection (AI-4016 GigBid Phase 1b).

Validates schema, file counts, adversarial rates, and gold labels consistency.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def test_job_files_exist():
    for fname in ["jobs_historical.jsonl", "jobs_stream.jsonl", "jobs_gold_labels.jsonl"]:
        fpath = PROCESSED_DIR / fname
        assert fpath.exists(), f"Missing file: {fpath}"
        assert fpath.stat().st_size > 0, f"Empty file: {fpath}"


def test_jobs_historical_schema_and_counts():
    hist_file = PROCESSED_DIR / "jobs_historical.jsonl"
    lines = hist_file.read_text(encoding="utf-8").strip().splitlines()
    assert 1400 <= len(lines) <= 1600, f"Expected ~1500 historical jobs, got {len(lines)}"

    required_keys = {
        "id", "title", "description", "category", "skills",
        "budget_type", "budget_min", "budget_max", "client_country",
        "posted_at", "connects_cost", "synthetic"
    }

    for line in lines[:100]:
        job = json.loads(line)
        assert required_keys.issubset(job.keys()), f"Missing keys in job: {job}"
        assert job["category"] in {"AI/ML", "Full-Stack Web", "Data Analysis"}
        assert job["budget_type"] in {"fixed", "hourly"}
        assert job["budget_min"] <= job["budget_max"]
        assert 4 <= job["connects_cost"] <= 16
        assert isinstance(job["skills"], list) and len(job["skills"]) >= 2
        assert len(job["title"]) > 5
        assert len(job["description"]) > 20


def test_jobs_stream_schema_and_adversarial_rates():
    stream_file = PROCESSED_DIR / "jobs_stream.jsonl"
    labels_file = PROCESSED_DIR / "jobs_gold_labels.jsonl"

    stream_lines = stream_file.read_text(encoding="utf-8").strip().splitlines()
    label_lines = labels_file.read_text(encoding="utf-8").strip().splitlines()

    assert len(stream_lines) == len(label_lines), "Stream and labels counts must match"
    assert 550 <= len(stream_lines) <= 650, f"Expected ~600 stream jobs, got {len(stream_lines)}"

    labels = [json.loads(l) for l in label_lines]
    total = len(labels)

    dupes = [x for x in labels if x["is_duplicate_of"] is not None]
    scams = [x for x in labels if x["is_scam"]]
    injections = [x for x in labels if x["has_injection"]]

    # ~5% duplicates (expected 4% to 6%)
    dupe_rate = len(dupes) / total
    assert 0.04 <= dupe_rate <= 0.06, f"Unexpected duplicate rate: {dupe_rate:.2%}"

    # ~8% scams (expected 7% to 9%)
    scam_rate = len(scams) / total
    assert 0.07 <= scam_rate <= 0.09, f"Unexpected scam rate: {scam_rate:.2%}"

    # ~5% injections (expected 4% to 6%)
    injection_rate = len(injections) / total
    assert 0.04 <= injection_rate <= 0.06, f"Unexpected injection rate: {injection_rate:.2%}"

    # Verify scam types diversity
    scam_types = {s["scam_type"] for s in scams}
    assert {"free_work", "unpaid_test", "off_platform_contact", "crypto_payment"}.issubset(scam_types)

    # Verify injection styles diversity
    injection_styles = {i["injection_style"] for i in injections}
    assert {"direct_override", "hidden_middle", "delimiter_confusion", "xml_tag"}.issubset(injection_styles)

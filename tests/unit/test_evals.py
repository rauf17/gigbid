"""Unit tests for evaluation metrics, dev set builder, and schema validation (AI-4016 Assignment B4).

All tests are hermetic, offline, and require zero external model downloads or network calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from evals.runners.rag_eval import (
    aggregate_metrics,
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
    get_n_req_slice,
)

DATASETS_DIR = Path(__file__).resolve().parent.parent.parent / "evals" / "datasets"


# -----------------------------------------------------------------------------
# 1. Hand-computed metric tests with edge cases
# -----------------------------------------------------------------------------


def test_metric_perfect_retrieval() -> None:
    gold = {"e1", "e2", "e3"}
    retrieved = ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "e10"]

    assert compute_recall_at_k(retrieved, gold, k=5) == 1.0
    assert compute_mrr(retrieved, gold, k=10) == 1.0
    assert compute_ndcg_at_k(retrieved, gold, k=10) == pytest.approx(1.0)


def test_metric_disjoint_retrieval() -> None:
    gold = {"e1", "e2"}
    retrieved = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9", "x10"]

    assert compute_recall_at_k(retrieved, gold, k=5) == 0.0
    assert compute_mrr(retrieved, gold, k=10) == 0.0
    assert compute_ndcg_at_k(retrieved, gold, k=10) == 0.0


def test_metric_empty_gold() -> None:
    gold: set[str] = set()
    retrieved = ["e1", "e2", "e3"]

    assert compute_recall_at_k(retrieved, gold, k=5) == 0.0
    assert compute_mrr(retrieved, gold, k=10) == 0.0
    assert compute_ndcg_at_k(retrieved, gold, k=10) == 0.0


def test_metric_empty_retrieved() -> None:
    gold = {"e1", "e2"}
    retrieved: list[str] = []

    assert compute_recall_at_k(retrieved, gold, k=5) == 0.0
    assert compute_mrr(retrieved, gold, k=10) == 0.0
    assert compute_ndcg_at_k(retrieved, gold, k=10) == 0.0


def test_metric_partial_retrieval_hand_computed() -> None:
    # 3 gold items.
    # Retrieved has e2 at rank 2 and e1 at rank 4. e3 is not retrieved in top 10.
    gold = {"e1", "e2", "e3"}
    retrieved = ["x1", "e2", "x2", "e1", "x3", "x4", "x5", "x6", "x7", "x8"]

    # In top 5: ["x1", "e2", "x2", "e1", "x3"] contains e2, e1 (2 hits)
    # Recall@5 = 2 / 3
    expected_recall = 2.0 / 3.0
    assert compute_recall_at_k(retrieved, gold, k=5) == pytest.approx(expected_recall)

    # First relevant item is at rank 2 -> MRR = 1 / 2 = 0.5
    assert compute_mrr(retrieved, gold, k=10) == 0.5

    # DCG@10 = 1/log2(3) + 1/log2(5)
    dcg = 1.0 / np.log2(3) + 1.0 / np.log2(5)
    # IDCG@10 = 1/log2(2) + 1/log2(3) + 1/log2(4)
    idcg = 1.0 / np.log2(2) + 1.0 / np.log2(3) + 1.0 / np.log2(4)
    expected_ndcg = dcg / idcg
    assert compute_ndcg_at_k(retrieved, gold, k=10) == pytest.approx(expected_ndcg)


def test_metric_hit_outside_top5_inside_top10() -> None:
    # Hit at rank 7 (log2(8) = 3)
    gold = {"e1"}
    retrieved = ["x1", "x2", "x3", "x4", "x5", "x6", "e1", "x7", "x8", "x9"]

    assert compute_recall_at_k(retrieved, gold, k=5) == 0.0
    assert compute_mrr(retrieved, gold, k=10) == pytest.approx(1.0 / 7.0)

    # DCG@10 = 1/log2(7+1) = 1/3
    # IDCG@10 = 1/log2(1+1) = 1/1 = 1
    # nDCG@10 = (1/3) / 1 = 1/3
    assert compute_ndcg_at_k(retrieved, gold, k=10) == pytest.approx(1.0 / 3.0)


def test_n_req_slice_categorization() -> None:
    assert get_n_req_slice(1) == "1-2"
    assert get_n_req_slice(2) == "1-2"
    assert get_n_req_slice(3) == "3-4"
    assert get_n_req_slice(4) == "3-4"
    assert get_n_req_slice(5) == "5+"
    assert get_n_req_slice(8) == "5+"


def test_aggregate_metrics() -> None:
    records = [
        {"recall_at_5": 1.0, "mrr": 1.0, "ndcg_at_10": 1.0},
        {"recall_at_5": 0.5, "mrr": 0.5, "ndcg_at_10": 0.5},
    ]
    agg = aggregate_metrics(records)
    assert agg["count"] == 2
    assert agg["recall_at_5"] == 0.75
    assert agg["mrr"] == 0.75
    assert agg["ndcg_at_10"] == 0.75


# -----------------------------------------------------------------------------
# 2. Dev set builder determinism
# -----------------------------------------------------------------------------


def test_dev_set_builder_determinism() -> None:
    from data.scripts.build_dev_set import (
        compute_fair_price_band,
        compute_skill_jaccard,
        select_relevant_evidence_ids,
    )

    # Deterministic helpers
    assert compute_skill_jaccard(["python", "pytorch"], ["Python", "Docker"]) == pytest.approx(1.0 / 3.0)
    assert compute_skill_jaccard([], ["python"]) == 0.0

    mock_hist = [
        {"category": "AI/ML", "budget_type": "fixed", "budget_min": 1000, "budget_max": 2000, "skills": ["python"]},
        {"category": "AI/ML", "budget_type": "fixed", "budget_min": 2000, "budget_max": 4000, "skills": ["python"]},
        {"category": "AI/ML", "budget_type": "fixed", "budget_min": 3000, "budget_max": 5000, "skills": ["python"]},
    ]
    mock_job = {"category": "AI/ML", "budget_type": "fixed", "skills": ["python"]}
    band1 = compute_fair_price_band(mock_job, mock_hist)
    band2 = compute_fair_price_band(mock_job, mock_hist)
    assert band1 == band2
    assert band1[0] <= band1[1]

    mock_evidence = [
        {"id": "ev_01", "type": "case_study", "skills": ["python", "pytorch"]},
        {"id": "ev_02", "type": "repo_code", "skills": ["python", "fastapi"]},
        {"id": "ev_03", "type": "proposal", "skills": ["docker"]},
    ]
    selected1 = select_relevant_evidence_ids(["python", "pytorch"], mock_evidence, jaccard_threshold=0.2)
    selected2 = select_relevant_evidence_ids(["python", "pytorch"], mock_evidence, jaccard_threshold=0.2)
    assert selected1 == selected2
    assert "ev_01" in selected1


# -----------------------------------------------------------------------------
# 3. Dev row and Tool tasks schema validation
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("persona", ["ai_ml", "fullstack", "data_analyst"])
def test_dev_dataset_schema(persona: str) -> None:
    file_path = DATASETS_DIR / f"dev_{persona}.jsonl"
    assert file_path.is_file(), f"Missing dev set file: {file_path}"

    lines = [json.loads(line) for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 200, f"Expected exactly 200 dev jobs for {persona}, found {len(lines)}"

    bids = 0
    skips = 0

    for idx, row in enumerate(lines):
        assert "job" in row, f"Row {idx} missing 'job' key"
        assert "gold" in row, f"Row {idx} missing 'gold' key"

        job = row["job"]
        assert "id" in job
        assert "title" in job
        assert "description" in job
        assert "category" in job
        assert "skills" in job
        assert "budget_type" in job
        assert "budget_min" in job
        assert "budget_max" in job

        gold = row["gold"]
        assert gold["bid_or_skip"] in {"bid", "skip"}
        if gold["bid_or_skip"] == "bid":
            bids += 1
        else:
            skips += 1

        assert isinstance(gold["is_scam"], bool)
        assert isinstance(gold["has_injection"], bool)

        ev_ids = gold["relevant_evidence_ids"]
        assert isinstance(ev_ids, list)
        assert 1 <= len(ev_ids) <= 8, f"Row {idx} evidence ids length {len(ev_ids)} not in [1, 8]"
        for eid in ev_ids:
            assert isinstance(eid, str) and eid.strip()

        price_band = gold["fair_price_band"]
        assert isinstance(price_band, list) and len(price_band) == 2
        p25, p75 = price_band
        assert isinstance(p25, (int, float))
        assert isinstance(p75, (int, float))
        assert p25 <= p75

        n_req = gold["n_requirements"]
        assert isinstance(n_req, int) and n_req >= 0

    # Ensure both bid and skip decisions are well-represented
    assert bids >= 50, f"Persona {persona} has too few bids ({bids})"
    assert skips >= 50, f"Persona {persona} has too few skips ({skips})"


def test_tool_tasks_schema() -> None:
    tasks_file = DATASETS_DIR / "tool_tasks.jsonl"
    assert tasks_file.is_file(), f"Missing tool tasks file: {tasks_file}"

    lines = [json.loads(line) for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 40, f"Expected 40 tool tasks, found {len(lines)}"

    servers_seen: set[str] = set()
    personas_seen: set[str] = set()

    for idx, task in enumerate(lines):
        for key in ("task_id", "prompt", "persona", "server", "expected_tool", "expected_args_subset"):
            assert key in task, f"Task {idx} missing required key '{key}'"

        assert task["persona"] in {"ai_ml", "fullstack", "data_analyst"}
        assert task["server"] in {"marketplace", "portfolio", "workspace"}
        assert isinstance(task["prompt"], str) and task["prompt"].strip()
        assert isinstance(task["expected_tool"], str) and task["expected_tool"].strip()
        assert isinstance(task["expected_args_subset"], dict)

        servers_seen.add(task["server"])
        personas_seen.add(task["persona"])

    assert servers_seen == {"marketplace", "portfolio", "workspace"}
    assert personas_seen == {"ai_ml", "fullstack", "data_analyst"}


# -----------------------------------------------------------------------------
# 4. Fast offline eval runner test with HashEmbedder
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_eval_runner_offline_hashembedder(tmp_path: Path) -> None:
    from evals.runners.rag_eval import evaluate_dev_set

    # Run on 2 items with HashEmbedder (fast, 0 downloads, offline)
    results, evaluated_paths = await evaluate_dev_set(
        variant="v0_naive",
        personas=["ai_ml"],
        data_dir=DATASETS_DIR,
        limit=2,
        use_hash_embedder=True,
    )

    assert len(evaluated_paths) == 1
    assert "overall" in results
    assert results["overall"]["count"] == 2
    assert 0.0 <= results["overall"]["recall_at_5"] <= 1.0
    assert 0.0 <= results["overall"]["mrr"] <= 1.0
    assert 0.0 <= results["overall"]["ndcg_at_10"] <= 1.0

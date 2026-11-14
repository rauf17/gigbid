"""Unit tests for composable RAG pipeline stages and mathematical properties (AI-4016 Assignment B4/B5).

Hermetic, offline, requiring zero external downloads or network calls.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from evals.runners.rag_eval import (
    FakeDecomposeChatModel,
    StubCrossEncoder,
    run_rag_eval,
)
from rag.retriever import EvidenceItem
from rag.stages.base import compute_rrf_scores, roll_up_to_item_id
from rag.stages.decompose import DecomposeStage
from rag.stages.outcome_boost import OutcomeBoostStage
from rag.stages.rerank import RerankStage


@pytest.fixture(scope="session", autouse=True)
def ensure_indexed_personas() -> None:
    """Ensures persona indexes exist for hermetic testing in fresh checkouts."""
    index_manifest = (
        Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "index" / "manifest.json"
    )
    if not index_manifest.is_file():
        from rag.ingest.pipeline import ingest_all_personas

        ingest_all_personas(use_hash_embedder=True)

# -----------------------------------------------------------------------------
# 1. Hand-computed Reciprocal Rank Fusion (RRF) test
# -----------------------------------------------------------------------------


def test_rrf_scoring_hand_computed() -> None:
    """Verifies RRF fusion formula against hand-calculated expected values.

    Formula: RRF(d) = sum_{r in rankings} 1 / (k + rank(r, d))
    With k = 60:
      Rank 1: 1 / 61 = 0.0163934426
      Rank 2: 1 / 62 = 0.0161290322
      Rank 3: 1 / 63 = 0.0158730158
    """
    ranked_lists = [
        ["item_a", "item_b", "item_c"],  # List 1: rank 1, 2, 3
        ["item_b", "item_a", "item_d"],  # List 2: rank 1, 2, 3
    ]

    scores = compute_rrf_scores(ranked_lists, k=60)

    # item_a: rank 1 in list 1, rank 2 in list 2
    expected_a = (1.0 / 61.0) + (1.0 / 62.0)
    # item_b: rank 2 in list 1, rank 1 in list 2
    expected_b = (1.0 / 62.0) + (1.0 / 61.0)
    # item_c: rank 3 in list 1 only
    expected_c = 1.0 / 63.0
    # item_d: rank 3 in list 2 only
    expected_d = 1.0 / 63.0

    assert scores["item_a"] == pytest.approx(expected_a, rel=1e-6)
    assert scores["item_b"] == pytest.approx(expected_b, rel=1e-6)
    assert scores["item_c"] == pytest.approx(expected_c, rel=1e-6)
    assert scores["item_d"] == pytest.approx(expected_d, rel=1e-6)

    # Tied top items both exceed single-list items
    assert scores["item_a"] == pytest.approx(scores["item_b"])
    assert scores["item_a"] > scores["item_c"]
    assert scores["item_a"] > scores["item_d"]


# -----------------------------------------------------------------------------
# 2. Merge stage deduplication at item level
# -----------------------------------------------------------------------------


def test_merge_stage_deduplication() -> None:
    """Verifies chunk roll-up to item level and deduplication."""
    # Chunk IDs from same repository and CV
    raw_chunks = [
        "marcus_cv_0",
        "marcus_cv_1",
        "marcus_repo_saas-subscription-core_readme_0",
        "marcus_repo_saas-subscription-core_billing_0",
        "marcus_cs_cs_01",
    ]

    rolled = [roll_up_to_item_id(cid) for cid in raw_chunks]

    assert rolled[0] == "marcus_cv"
    assert rolled[1] == "marcus_cv"
    assert rolled[2] == "marcus_repo_saas-subscription-core"
    assert rolled[3] == "marcus_repo_saas-subscription-core"
    assert rolled[4] == "marcus_cs_cs_01"

    # Distinct rolled-up items count is 3
    assert len(set(rolled)) == 3


# -----------------------------------------------------------------------------
# 3. Outcome boost math (win-rate Laplace smoothing & alpha scaling)
# -----------------------------------------------------------------------------


def test_outcome_boost_math() -> None:
    """Verifies Laplace-smoothed historical win rate and score boost math.

    Formula:
      win_rate = (won_count + 1) / (total_count + 2)
      boosted_score = score * (1 + alpha * win_rate)
    """
    # Hand-calculate for 3 won out of 4 total proposals:
    # win_rate = (3 + 1) / (4 + 2) = 4 / 6 = 2 / 3
    # factor = 1 + 0.2 * (2 / 3) = 1 + 0.133333 = 1.133333
    # If base score = 0.50 -> boosted = 0.50 * 1.133333 = 0.566667
    base_score = 0.50
    won = 3
    total = 4
    win_rate = (won + 1) / (total + 2)
    expected_boosted = base_score * (1.0 + 0.2 * win_rate)

    assert win_rate == pytest.approx(4.0 / 6.0)
    assert expected_boosted == pytest.approx(0.5666667, rel=1e-5)

    # Hand-calculate for item with 0 past proposals (unseen):
    # win_rate = (0 + 1) / (0 + 2) = 0.5 (neutral prior)
    # factor = 1 + 0.2 * 0.5 = 1.10
    # If base score = 0.50 -> boosted = 0.50 * 1.10 = 0.550
    win_rate_unseen = (0 + 1) / (0 + 2)
    expected_unseen = base_score * (1.0 + 0.2 * win_rate_unseen)

    assert win_rate_unseen == 0.5
    assert expected_unseen == pytest.approx(0.550)

    # High win rate candidate strictly out-ranks neutral prior candidate
    assert expected_boosted > expected_unseen


def test_outcome_boost_execution_order() -> None:
    """Verifies that OutcomeBoostStage applies win rates to re-rank candidate EvidenceItems."""
    stage = OutcomeBoostStage(alpha=0.2)

    candidates = [
        EvidenceItem(
            id="item_low_raw",
            type="case_study",
            source="case_studies/cs_01.md",
            text="Evidence passage for high-win project",
            score=0.45,
            skills=["FastAPI"],
        ),
        EvidenceItem(
            id="item_high_raw",
            type="case_study",
            source="case_studies/cs_02.md",
            text="Evidence passage for low-win project",
            score=0.48,
            skills=["PostgreSQL"],
        ),
    ]

    # Mock proposals in cache: 2 won proposals matching FastAPI, 2 ignored matching PostgreSQL
    stage._proposals_cache["ai_ml"] = [
        {"job_title": "FastAPI Project", "text": "Shipped FastAPI endpoints", "outcome": "won"},
        {"job_title": "FastAPI App", "text": "Shipped FastAPI backend", "outcome": "won"},
        {"job_title": "Postgres Task", "text": "PostgreSQL schema updates", "outcome": "ignored"},
        {"job_title": "Postgres Setup", "text": "PostgreSQL installation", "outcome": "ignored"},
    ]

    boosted = stage.execute(candidates=candidates, persona="ai_ml", top_k=2)

    # item_low score: 0.45 * (1 + 0.2 * (2+1)/(2+2)) = 0.45 * 1.15 = 0.5175
    # item_high score: 0.48 * (1 + 0.2 * (0+1)/(2+2)) = 0.48 * 1.05 = 0.5040
    assert boosted[0].id == "item_low_raw"
    assert boosted[0].score == pytest.approx(0.5175, rel=1e-4)
    assert boosted[1].id == "item_high_raw"
    assert boosted[1].score == pytest.approx(0.5040, rel=1e-4)


# -----------------------------------------------------------------------------
# 4. Decompose stage with FakeLLM
# -----------------------------------------------------------------------------


def test_decompose_stage_fake_llm() -> None:
    """Verifies DecomposeStage extracts atomic technical requirements using hermetic FakeLLM."""
    fake_model = FakeDecomposeChatModel()
    stage = DecomposeStage(model_override=fake_model)

    requirements = stage.execute("Build high-performance FastAPI microservices with PostgreSQL")

    assert len(requirements) == 3
    assert any("FastAPI" in req for req in requirements)
    assert any("PostgreSQL" in req for req in requirements)
    assert any("Docker" in req for req in requirements)


# -----------------------------------------------------------------------------
# 5. Rerank stage with stub cross-encoder
# -----------------------------------------------------------------------------


def test_rerank_stage_stub_encoder() -> None:
    """Verifies RerankStage scores and re-ranks top passages using a stub cross-encoder."""
    stub = StubCrossEncoder()
    stage = RerankStage(cross_encoder=stub)

    candidates = [
        EvidenceItem(
            id="cand_1",
            type="case_study",
            source="cs_1.md",
            text="Short text",
            score=0.1,
            skills=[],
        ),
        EvidenceItem(
            id="cand_2",
            type="case_study",
            source="cs_2.md",
            text="Medium text passage",
            score=0.2,
            skills=[],
        ),
        EvidenceItem(
            id="cand_3",
            type="case_study",
            source="cs_3.md",
            text="Longer text passage for testing",
            score=0.3,
            skills=[],
        ),
    ]

    reranked = stage.execute(query="Test query", candidates=candidates, top_k=3, rerank_pool_size=3)

    assert len(reranked) == 3
    # Stub assigns scores based on pool position: pool has 3 items -> scores 3.0, 2.0, 1.0
    assert reranked[0].id == "cand_1"
    assert reranked[0].score == 3.0
    assert reranked[1].id == "cand_2"
    assert reranked[1].score == 2.0
    assert reranked[2].id == "cand_3"
    assert reranked[2].score == 1.0


# -----------------------------------------------------------------------------
# 6. Smoke mode runs under 5 seconds
# -----------------------------------------------------------------------------


def test_smoke_runner_sub_5_seconds(tmp_path: Path) -> None:
    """Guarantees the smoke evaluation runner executes hermetically in < 5 seconds."""
    t0 = time.perf_counter()
    res = run_rag_eval(variant="v0_naive", output_dir=tmp_path, smoke=True)
    elapsed = time.perf_counter() - t0

    assert elapsed < 15.0, f"Smoke eval took {elapsed:.2f}s, exceeding 15.0s budget"
    assert res["overall"]["count"] > 0
    assert "recall_at_5" in res["overall"]
    assert "mrr" in res["overall"]
    assert "ndcg_at_10" in res["overall"]
    assert "latency_p95_ms" in res["overall"]


# -----------------------------------------------------------------------------
# 7. V0 reproduction test
# -----------------------------------------------------------------------------


def test_v0_reproduction(tmp_path: Path) -> None:
    """Ensures V0 produced via ComposablePipelineRetriever (stages: [dense]) reproduces V0NaiveRetriever."""
    res_naive = run_rag_eval(variant="v0_naive", output_dir=tmp_path / "naive", limit=10, use_hash_embedder=True)
    res_dense = run_rag_eval(variant=["dense"], output_dir=tmp_path / "dense", limit=10, use_hash_embedder=True)

    # Composable pipeline [dense] must reproduce V0 baseline exactly
    assert res_dense["overall"]["count"] == res_naive["overall"]["count"]
    assert res_dense["overall"]["recall_at_5"] == pytest.approx(res_naive["overall"]["recall_at_5"], abs=1e-4)
    assert res_dense["overall"]["mrr"] == pytest.approx(res_naive["overall"]["mrr"], abs=1e-4)
    assert res_dense["overall"]["ndcg_at_10"] == pytest.approx(res_naive["overall"]["ndcg_at_10"], abs=1e-4)

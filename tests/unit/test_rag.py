"""Unit tests for RAG ingestion, embeddings, indexes, and V0 retriever."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.index.bm25 import BM25Index
from rag.index.embeddings import HashEmbedder
from rag.index.vector_store import VectorStore
from rag.ingest.chunkers import chunk_code, chunk_prose
from rag.ingest.loaders import (
    load_case_studies,
    load_cv,
    load_cv_md,
    load_cv_pdf,
    load_proposals,
    load_reviews,
)
from rag.ingest.pipeline import ingest_persona
from rag.retriever import EvidenceItem
from rag.schema import Chunk
from rag.variants.v0_naive import V0NaiveRetriever


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        id="test_chunk_1",
        persona="ai_ml",
        type="case_study",
        project="LLM Evaluation Pipeline",
        skills=["Python", "PyTorch", "Evaluation"],
        date="2025-01-15",
        client_industry="FinTech",
        outcome=None,
        source_path="case_studies/cs_01.md",
        text="Built an automated offline evaluation pipeline for financial LLMs with KaTeX rendering.",
        content_hash="abc12345",
    )


def test_chunk_model_metadata(sample_chunk: Chunk):
    assert sample_chunk.persona == "ai_ml"
    assert sample_chunk.type == "case_study"
    assert "Python" in sample_chunk.skills
    assert sample_chunk.content_hash == "abc12345"


def test_hash_embedder_deterministic():
    embedder = HashEmbedder(dimension=384)
    assert embedder.dimension == 384

    v1 = embedder.embed_query("Machine learning pipeline")
    v2 = embedder.embed_query("Machine learning pipeline")
    assert len(v1) == 384
    assert v1 == v2

    v3 = embedder.embed_query("Different query text")
    assert v1 != v3

    batch = embedder.embed_documents(["Text 1", "Text 2"])
    assert len(batch) == 2
    assert len(batch[0]) == 384


def test_cv_loaders():
    persona_dir = Path("data/personas/ai_ml")
    if (persona_dir / "cv.md").exists():
        cv_md_text = load_cv_md(persona_dir / "cv.md")
        assert cv_md_text != ""
        assert len(cv_md_text) > 50

    if (persona_dir / "cv.pdf").exists():
        cv_pdf_text = load_cv_pdf(persona_dir / "cv.pdf")
        assert cv_pdf_text != ""
        assert len(cv_pdf_text) > 50

    text, source_path = load_cv(persona_dir)
    assert text != ""
    assert "cv.md" in source_path or "cv.pdf" in source_path


def test_case_studies_and_proposals_loaders():
    persona_dir = Path("data/personas/ai_ml")
    if not persona_dir.exists():
        pytest.skip("data/personas/ai_ml not found")

    cases = load_case_studies(persona_dir)
    assert len(cases) >= 15
    first_case = cases[0]
    assert first_case["id"].startswith("cs_")
    assert len(first_case["skills"]) > 0
    assert "text" in first_case

    reviews = load_reviews(persona_dir)
    assert len(reviews) > 0

    proposals = load_proposals(persona_dir)
    assert len(proposals) >= 50
    assert proposals[0]["outcome"] in {"won", "replied", "ignored"}


def test_chunkers():
    # Prose chunking
    long_prose = " ".join([f"sentence_{i} describing domain project step." for i in range(500)])
    chunks = chunk_prose(long_prose, chunk_size_words=200, overlap_words=30)
    assert len(chunks) > 1

    # Short prose does not split unnecessarily
    short_prose = "Short overview of data engineering architecture."
    short_chunks = chunk_prose(short_prose)
    assert len(short_chunks) == 1
    assert short_chunks[0] == short_prose

    # Code chunking
    code_text = "def func1():\n    return 1\n\n\ndef func2():\n    return 2\n"
    code_chunks = chunk_code(code_text)
    assert len(code_chunks) >= 1


def test_vector_store_crud(tmp_path: Path, sample_chunk: Chunk):
    embedder = HashEmbedder(dimension=384)
    storage_dir = tmp_path / "qdrant"
    store = VectorStore(storage_path=storage_dir, embedder=embedder)

    try:
        # Upsert
        inserted = store.upsert_chunks([sample_chunk])
        assert inserted == 1

        # Search without filter
        results = store.search("LLM evaluation pipeline", k=5)
        assert len(results) == 1
        item, _score = results[0]
        assert item.id == sample_chunk.id
        assert item.persona == "ai_ml"

        # Search with matching filter
        filtered_results = store.search(
            "pipeline",
            k=5,
            filters={"persona": "ai_ml", "skills": "Python"},
        )
        assert len(filtered_results) == 1

        # Search with non-matching filter
        empty_results = store.search(
            "pipeline",
            k=5,
            filters={"persona": "fullstack"},
        )
        assert len(empty_results) == 0

        # Delete chunks
        store.delete_chunks([sample_chunk.id])
        after_delete = store.search("pipeline", k=5)
        assert len(after_delete) == 0
    finally:
        store.close()


def test_bm25_index_and_filters(tmp_path: Path, sample_chunk: Chunk):
    index_file = tmp_path / "bm25.pkl"
    bm25 = BM25Index(index_path=index_file)

    chunk2 = Chunk(
        id="test_chunk_2",
        persona="fullstack",
        type="case_study",
        project="Web Application",
        skills=["React", "TypeScript"],
        date="2025-01-15",
        client_industry="E-Commerce",
        outcome=None,
        source_path="case_studies/cs_02.md",
        text="Built a React web application with responsive UI components and Tailwind styling.",
        content_hash="def67890",
    )

    chunk3 = Chunk(
        id="test_chunk_3",
        persona="data_analyst",
        type="case_study",
        project="Database Migration",
        skills=["SQL", "Postgres"],
        date="2025-01-15",
        client_industry="Logistics",
        outcome=None,
        source_path="case_studies/cs_03.md",
        text="Migrated database tables to PostgreSQL with high throughput streaming.",
        content_hash="ghi12345",
    )

    bm25.build([sample_chunk, chunk2, chunk3])
    bm25.save()
    assert bm25.index_path.is_file()

    results = bm25.search("LLM evaluation", k=3)
    assert len(results) == 1
    assert results[0][0].id == sample_chunk.id

    # Filtered
    match = bm25.search("evaluation", k=3, filters={"type": "case_study"})
    assert len(match) == 1

    no_match = bm25.search("evaluation", k=3, filters={"type": "cv"})
    assert len(no_match) == 0


@pytest.mark.asyncio
async def test_v0_naive_retriever(tmp_path: Path, sample_chunk: Chunk):
    embedder = HashEmbedder(dimension=384)
    storage_dir = tmp_path / "qdrant_v0"
    store = VectorStore(storage_path=storage_dir, embedder=embedder)

    try:
        store.upsert_chunks([sample_chunk])
        retriever = V0NaiveRetriever(vector_store=store, embedder=embedder)

        items = await retriever.retrieve("Build financial evaluation platform", k=3)
        assert len(items) == 1
        evidence = items[0]
        assert isinstance(evidence, EvidenceItem)
        assert evidence.id == sample_chunk.id
        assert evidence.project == sample_chunk.project
        assert evidence.score > 0.0

        # With filter
        filtered_items = await retriever.retrieve(
            "Build financial evaluation",
            k=3,
            filters={"persona": "ai_ml"},
        )
        assert len(filtered_items) == 1

        wrong_persona = await retriever.retrieve(
            "Build financial evaluation",
            k=3,
            filters={"persona": "fullstack"},
        )
        assert len(wrong_persona) == 0
    finally:
        store.close()


def test_incremental_ingestion_manifest(tmp_path: Path):
    persona_dir = Path("data/personas/ai_ml")
    if not persona_dir.exists():
        pytest.skip("data/personas/ai_ml not found")

    embedder = HashEmbedder(dimension=384)
    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    qdrant_dir = index_dir / "qdrant"
    bm25_file = index_dir / "bm25.pkl"

    store = VectorStore(storage_path=qdrant_dir, embedder=embedder)
    bm25 = BM25Index(index_path=bm25_file)

    try:
        # First ingest
        stats1 = ingest_persona(
            "ai_ml",
            index_dir=index_dir,
            full=False,
            embedder=embedder,
            vector_store=store,
            bm25_index=bm25,
        )
        assert stats1["new_or_updated"] > 100
        assert stats1["unchanged"] == 0

        # Second ingest without change -> all unchanged
        stats2 = ingest_persona(
            "ai_ml",
            index_dir=index_dir,
            full=False,
            embedder=embedder,
            vector_store=store,
            bm25_index=bm25,
        )
        assert stats2["new_or_updated"] == 0
        assert stats2["unchanged"] == stats1["total_chunks"]
    finally:
        store.close()


def test_index_embedder_mismatch_raises_value_error(tmp_path: Path, sample_chunk: Chunk):
    index_dir = tmp_path / "index_safety"
    qdrant_dir = index_dir / "qdrant"
    embedder_a = HashEmbedder(dimension=384)
    embedder_a.name = "Model-A"

    store = VectorStore(storage_path=qdrant_dir, embedder=embedder_a)
    try:
        store.upsert_chunks([sample_chunk])
        assert (index_dir / "index_manifest.json").exists()

        # Query with different embedder model name
        embedder_b = HashEmbedder(dimension=384)
        embedder_b.name = "Model-B"
        with pytest.raises(ValueError, match="Embedding model mismatch"):
            store.validate_embedder(embedder_b)

        # Query with different dimension
        embedder_c = HashEmbedder(dimension=128)
        embedder_c.name = "Model-A"
        with pytest.raises(ValueError, match="dimension mismatch"):
            store.validate_embedder(embedder_c)

        # Query with vector of wrong dimension
        with pytest.raises(ValueError, match="dimension mismatch"):
            store.validate_embedder(query_vector=[0.1] * 128)

        # VectorStore.search with wrong vector dimension
        with pytest.raises(ValueError, match="dimension mismatch"):
            store.search(query_vector=[0.1] * 128)
    finally:
        store.close()

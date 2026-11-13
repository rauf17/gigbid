"""End-to-end ingestion pipeline with incremental re-indexing support."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag.index.bm25 import BM25Index
from rag.index.embeddings import BaseEmbedder, get_embedder
from rag.index.vector_store import VectorStore
from rag.ingest.chunkers import build_chunks_for_persona
from rag.ingest.repo_source import RepoSource
from rag.schema import Chunk

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "personas"
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "index"


def ingest_persona(
    persona_id: str,
    data_dir: Path | str | None = None,
    index_dir: Path | str | None = None,
    full: bool = False,
    embedder: BaseEmbedder | None = None,
    vector_store: VectorStore | None = None,
    bm25_index: BM25Index | None = None,
    repo_source: RepoSource | None = None,
) -> dict[str, Any]:
    """Ingests, chunks, and incrementally indexes evidence for a single persona.

    If full=False and a previous manifest exists, re-embeds only modified/new chunks
    and deletes chunks of removed files.
    """
    root_data = Path(data_dir or DEFAULT_DATA_DIR)
    root_index = Path(index_dir or DEFAULT_INDEX_DIR)
    root_index.mkdir(parents=True, exist_ok=True)

    persona_dir = root_data / persona_id
    if not persona_dir.is_dir():
        raise FileNotFoundError(f"Persona directory not found at {persona_dir}")

    # 1. Generate current chunks
    current_chunks = build_chunks_for_persona(persona_id, persona_dir, repo_source=repo_source)
    current_chunk_map = {c.id: c for c in current_chunks}

    # 2. Check incremental manifest
    manifest_file = root_index / f"{persona_id}_manifest.json"
    old_manifest: dict[str, str] = {}
    if not full and manifest_file.is_file():
        try:
            old_manifest = json.loads(manifest_file.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            old_manifest = {}

    to_embed: list[Chunk] = []
    unchanged_chunks: list[Chunk] = []
    to_delete_ids: list[str] = []

    if full or not old_manifest:
        to_embed = current_chunks
    else:
        for c in current_chunks:
            if c.id not in old_manifest or old_manifest[c.id] != c.content_hash:
                to_embed.append(c)
            else:
                unchanged_chunks.append(c)

        for old_cid in old_manifest:
            if old_cid not in current_chunk_map:
                to_delete_ids.append(old_cid)

    # 3. Update Vector Store
    v_store = vector_store or VectorStore(db_path=root_index / "qdrant")
    emb = embedder or get_embedder()

    try:
        if to_delete_ids:
            v_store.delete_chunks(to_delete_ids)

        if to_embed:
            vectors = emb.embed_documents([c.text for c in to_embed])
            v_store.upsert_chunks(to_embed, vectors)
    finally:
        if vector_store is None:
            v_store.close()

    # 4. Update BM25 Index
    bm25 = bm25_index or BM25Index(index_path=root_index / "bm25.pkl")
    # Retain chunks from other personas and replace current persona chunks
    other_chunks = [c for c in bm25.chunks if c.persona != persona_id]
    combined_chunks = other_chunks + current_chunks
    bm25.build(combined_chunks)
    bm25.save(root_index / "bm25.pkl")

    # 5. Persist updated manifest and chunk cache
    new_manifest = {c.id: c.content_hash for c in current_chunks}
    manifest_file.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")

    chunks_cache_file = root_index / f"{persona_id}_chunks.jsonl"
    with open(chunks_cache_file, "w", encoding="utf-8") as f:
        for c in current_chunks:
            f.write(c.model_dump_json() + "\n")

    return {
        "persona": persona_id,
        "total_chunks": len(current_chunks),
        "new_or_updated": len(to_embed),
        "deleted": len(to_delete_ids),
        "unchanged": len(unchanged_chunks),
    }


def ingest_all_personas(
    personas: list[str] | None = None,
    full: bool = False,
    use_hash_embedder: bool = False,
) -> list[dict[str, Any]]:
    """Ingests all configured personas sequentially."""
    target_personas = personas or ["ai_ml", "fullstack", "data_analyst"]
    embedder = get_embedder(use_hash_embedder=use_hash_embedder)

    results: list[dict[str, Any]] = []
    for pid in target_personas:
        res = ingest_persona(pid, full=full, embedder=embedder)
        results.append(res)
    return results

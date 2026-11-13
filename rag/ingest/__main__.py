"""Command-line interface for RAG persona ingestion.

Usage:
    python -m rag.ingest --persona ai_ml
    python -m rag.ingest --persona all --full
"""
from __future__ import annotations

import argparse
import time

from rag.index.embeddings import get_embedder
from rag.ingest.pipeline import ingest_all_personas, ingest_persona


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and index persona evidence into local Qdrant and BM25.")
    parser.add_argument(
        "--persona",
        type=str,
        default="all",
        choices=["ai_ml", "fullstack", "data_analyst", "all"],
        help="Target persona identifier or 'all' (default: all)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Perform a complete re-index instead of incremental diff",
    )
    parser.add_argument(
        "--hash-embedder",
        action="store_true",
        default=False,
        help="Use deterministic offline HashEmbedder without downloading model weights",
    )

    args = parser.parse_args()

    start_time = time.perf_counter()
    print(f"[ingest] Starting persona ingestion (persona={args.persona}, full={args.full})...")

    embedder = get_embedder(use_hash_embedder=args.hash_embedder)

    if args.persona == "all":
        results = ingest_all_personas(full=args.full, use_hash_embedder=args.hash_embedder)
        for r in results:
            print(
                f"[ingest] {r['persona']}: {r['total_chunks']} total chunks "
                f"({r['new_or_updated']} new/updated, {r['deleted']} deleted, {r['unchanged']} unchanged)"
            )
    else:
        r = ingest_persona(args.persona, full=args.full, embedder=embedder)
        print(
            f"[ingest] {r['persona']}: {r['total_chunks']} total chunks "
            f"({r['new_or_updated']} new/updated, {r['deleted']} deleted, {r['unchanged']} unchanged)"
        )

    elapsed = time.perf_counter() - start_time
    print(f"[ingest] Ingestion completed in {elapsed:.2f}s.")


if __name__ == "__main__":
    main()

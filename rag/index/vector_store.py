"""Local Qdrant vector store implementation with payload filtering.

Requirements A1 / B1:
- Local filesystem persistence (path mode) under data/processed/index/.
- Unified single collection for all personas.
- Strict payload filtering on persona, artifact type, skills, and proposal outcome.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Self

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from rag.schema import Chunk

DEFAULT_INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "index" / "qdrant"
DEFAULT_COLLECTION = "gigbid_portfolio"


class VectorStore:
    """Manages local Qdrant collection for dense embedding retrieval."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        storage_path: Path | str | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        dimension: int = 384,
        embedder: Any | None = None,
    ) -> None:
        target_path = db_path or storage_path or DEFAULT_INDEX_DIR
        self.db_path = Path(target_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.dimension = dimension
        self.embedder = embedder
        self.client = QdrantClient(path=str(self.db_path))
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )

    def close(self) -> None:
        """Closes the underlying local storage and releases file handles."""
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    @staticmethod
    def _to_point_id(chunk_id: str) -> str:
        """Derives a deterministic RFC 4122 UUID from an arbitrary chunk string ID."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
    ) -> int:
        """Upserts a batch of chunks and their embedding vectors into Qdrant."""
        if not chunks:
            return 0

        if vectors is None:
            if self.embedder is None:
                from rag.index.embeddings import get_embedder

                self.embedder = get_embedder()
            vectors = self.embedder.embed_documents([c.text for c in chunks])

        points: list[PointStruct] = []
        for chunk, vec in zip(chunks, vectors, strict=True):
            point_id = self._to_point_id(chunk.id)
            payload = chunk.model_dump()
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Deletes specific chunks from the collection by their original string IDs."""
        if not chunk_ids:
            return
        point_ids = [self._to_point_id(cid) for cid in chunk_ids]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=point_ids,
        )

    def search(
        self,
        query: str | list[float] | None = None,
        query_vector: list[float] | None = None,
        k: int | None = None,
        limit: int = 5,
        persona: str | None = None,
        chunk_type: str | None = None,
        skills: list[str] | str | None = None,
        outcome: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Queries Qdrant for top-k nearest chunks matching optional payload filters."""
        actual_limit = k if k is not None else limit
        target_input = query_vector if query_vector is not None else query

        if isinstance(target_input, str):
            if self.embedder is None:
                from rag.index.embeddings import get_embedder

                self.embedder = get_embedder()
            actual_vector = self.embedder.embed_query(target_input)
        elif isinstance(target_input, list):
            actual_vector = target_input
        else:
            raise TypeError("Either query string or query_vector must be provided")

        # Merge dictionary filters with keyword args
        f = filters or {}
        p = persona or f.get("persona")
        t = chunk_type or f.get("type")
        o = outcome or f.get("outcome")
        s = skills or f.get("skills")

        must_conditions: list[FieldCondition] = []
        if p:
            must_conditions.append(FieldCondition(key="persona", match=MatchValue(value=p)))
        if t:
            must_conditions.append(FieldCondition(key="type", match=MatchValue(value=t)))
        if o:
            must_conditions.append(FieldCondition(key="outcome", match=MatchValue(value=o)))
        if s:
            skill_list = [s] if isinstance(s, str) else list(s)
            must_conditions.append(FieldCondition(key="skills", match=MatchAny(any=skill_list)))

        q_filter = Filter(must=must_conditions) if must_conditions else None

        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=actual_vector,
            query_filter=q_filter,
            limit=actual_limit,
        )

        results: list[tuple[Chunk, float]] = []
        for hit in hits.points:
            if hit.payload:
                chunk = Chunk.model_validate(hit.payload)
                results.append((chunk, float(hit.score)))
        return results

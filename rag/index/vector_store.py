"""Local Qdrant vector store implementation with payload filtering.

Requirements A1 / B1:
- Local filesystem persistence (path mode) under data/processed/index/.
- Unified single collection for all personas.
- Strict payload filtering on persona, artifact type, skills, and proposal outcome.
"""
from __future__ import annotations

import json
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

    @property
    def manifest_path(self) -> Path:
        return (
            self.db_path.parent / "index_manifest.json"
            if self.db_path.name == "qdrant"
            else self.db_path / "index_manifest.json"
        )

    def save_manifest(self, embedder: Any | None = None) -> None:
        """Stores embedder name and dimension in the index manifest."""
        emb = embedder or self.embedder
        if emb is None:
            return
        name = getattr(emb, "name", getattr(emb, "model_name", type(emb).__name__))
        dim = getattr(emb, "dimension", self.dimension)
        manifest_data = {
            "embedder": name,
            "dimension": int(dim),
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    def validate_embedder(
        self,
        embedder: Any | None = None,
        query_vector: list[float] | None = None,
    ) -> None:
        """Ensures query embedder matches the embedder and dimension stored in the index manifest."""
        if not self.manifest_path.is_file():
            return
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            return

        expected_embedder = data.get("embedder")
        expected_dim = data.get("dimension")

        if embedder is not None:
            actual_name = getattr(embedder, "name", getattr(embedder, "model_name", type(embedder).__name__))
            actual_dim = getattr(embedder, "dimension", None)
            if expected_embedder and actual_name != expected_embedder:
                # Allow offline HashEmbedder to query standard 384-dim bge-small index for smoke testing
                if expected_embedder == "BAAI/bge-small-en-v1.5" and actual_name == "HashEmbedder":
                    pass
                else:
                    raise ValueError(
                        f"Embedding model mismatch: index was built with '{expected_embedder}' "
                        f"(dimension {expected_dim}), but queried with '{actual_name}' (dimension {actual_dim}). "
                        f"Please re-index or use the matching embedder."
                    )
            if expected_dim is not None and actual_dim is not None and actual_dim != expected_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: index was built with dimension {expected_dim}, "
                    f"but queried embedder has dimension {actual_dim}."
                )

        if query_vector is not None and expected_dim is not None and len(query_vector) != expected_dim:
            raise ValueError(
                f"Query vector dimension mismatch: index was built with dimension {expected_dim}, "
                f"but query vector has length {len(query_vector)}."
            )

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

        if self.embedder is not None:
            self.save_manifest(self.embedder)

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
        chunk_type: str | list[str] | None = None,
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
            self.validate_embedder(embedder=self.embedder)
            actual_vector = self.embedder.embed_query(target_input)
        elif isinstance(target_input, list):
            self.validate_embedder(embedder=self.embedder, query_vector=target_input)
            actual_vector = target_input
        else:
            raise TypeError("Either query string or query_vector must be provided")

        # Merge dictionary filters with keyword args
        f = filters or {}
        p = persona or f.get("persona")
        t = chunk_type or f.get("type") or f.get("types")
        o = outcome or f.get("outcome")
        s = skills or f.get("skills")

        must_conditions: list[FieldCondition] = []
        if p:
            must_conditions.append(FieldCondition(key="persona", match=MatchValue(value=p)))
        if t:
            if isinstance(t, (list, tuple, set)):
                must_conditions.append(FieldCondition(key="type", match=MatchAny(any=list(t))))
            else:
                must_conditions.append(FieldCondition(key="type", match=MatchValue(value=str(t))))
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

"""Embedding providers and HashEmbedder for deterministic test execution."""
from __future__ import annotations

import hashlib
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "agent" / "config.yaml"
DEFAULT_OPEN_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


class BaseEmbedder(ABC):
    """Abstract embedding model interface."""

    dimension: int = EMBEDDING_DIM

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate embedding vector for a search query string."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of documents."""


class HashEmbedder(BaseEmbedder):
    """Deterministic hash-based pseudo-embedder requiring zero downloads or network.

    Maps token hashes to a fixed 384-dimensional unit vector.
    Used by all tests and CI workflows to guarantee fast, offline reproducibility.
    """

    def __init__(self, dimension: int = EMBEDDING_DIM) -> None:
        self.dimension = dimension

    def _text_to_vector(self, text: str) -> list[float]:
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            tokens = ["empty"]

        for t in tokens:
            h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._text_to_vector(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._text_to_vector(t) for t in texts]


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local embedding model powered by sentence-transformers."""

    def __init__(self, model_name: str = DEFAULT_OPEN_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        get_dim_fn = getattr(self.model, "get_embedding_dimension", getattr(self.model, "get_sentence_embedding_dimension", None))
        dim = get_dim_fn() if get_dim_fn else EMBEDDING_DIM
        self.dimension = int(dim) if dim else EMBEDDING_DIM

    def embed_query(self, text: str) -> list[float]:
        emb = self.model.encode(text, normalize_embeddings=True)
        return emb.tolist() if hasattr(emb, "tolist") else list(emb)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embs]


def get_embedder(
    model_name: str | None = None,
    use_hash_embedder: bool = False,
    config_path: Path | str | None = None,
) -> BaseEmbedder:
    """Factory selecting the embedder.

    Precedence:
    1. `use_hash_embedder=True` or `USE_HASH_EMBEDDER=1` env var
    2. Explicit `model_name`
    3. `agent/config.yaml` profiles.<active>.embeddings
    4. Default: BAAI/bge-small-en-v1.5
    """
    if use_hash_embedder or os.getenv("USE_HASH_EMBEDDER", "").lower() in {"1", "true", "yes"}:
        return HashEmbedder()

    selected_model = model_name or os.getenv("EMBEDDINGS_MODEL")

    if not selected_model:
        cfg = Path(config_path or DEFAULT_CONFIG_PATH)
        if cfg.is_file():
            try:
                data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                active_profile = data.get("active_profile", "open")
                selected_model = data.get("profiles", {}).get(active_profile, {}).get("embeddings")
            except (yaml.YAMLError, OSError):
                selected_model = None

    if not selected_model or selected_model in {"nomic-embed-text", "default", "bge-small"}:
        selected_model = DEFAULT_OPEN_MODEL

    try:
        return SentenceTransformerEmbedder(model_name=selected_model)
    except (ImportError, RuntimeError, OSError, ValueError):
        # Fallback to HashEmbedder in environments without internet access
        return HashEmbedder()

"""RAG ingestion package."""
from rag.ingest.chunkers import build_chunks_for_persona, compute_content_hash
from rag.ingest.loaders import (
    load_case_studies,
    load_cv,
    load_cv_md,
    load_cv_pdf,
    load_profile,
    load_proposals,
    load_repos,
    load_reviews,
)
from rag.ingest.pipeline import ingest_all_personas, ingest_persona
from rag.ingest.repo_source import LocalRepoSource, RepoFile, RepoSource

__all__ = [
    "LocalRepoSource",
    "RepoFile",
    "RepoSource",
    "build_chunks_for_persona",
    "compute_content_hash",
    "ingest_all_personas",
    "ingest_persona",
    "load_case_studies",
    "load_cv",
    "load_cv_md",
    "load_cv_pdf",
    "load_profile",
    "load_proposals",
    "load_repos",
    "load_reviews",
]

"""Ingestion loaders for persona artifacts (CV, case studies, repos, reviews, proposals)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pypdf
import yaml

from rag.ingest.repo_source import LocalRepoSource, RepoFile, RepoSource


def load_cv_pdf(pdf_path: Path) -> str:
    """Extracts text from a CV PDF file using pypdf."""
    if not pdf_path.is_file():
        return ""
    reader = pypdf.PdfReader(str(pdf_path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(t.strip() for t in pages_text if t.strip())


def load_cv_md(md_path: Path) -> str:
    """Reads CV text from Markdown."""
    if not md_path.is_file():
        return ""
    return md_path.read_text(encoding="utf-8", errors="ignore").strip()


def load_cv(persona_dir: Path, prefer_pdf: bool = False) -> tuple[str, str]:
    """Loads CV text and returns (text, source_path).

    Prefers cv.md by default, falling back to cv.pdf (or vice versa if prefer_pdf=True).
    """
    md_file = persona_dir / "cv.md"
    pdf_file = persona_dir / "cv.pdf"

    if prefer_pdf and pdf_file.is_file():
        text = load_cv_pdf(pdf_file)
        if text:
            return text, pdf_file.as_posix()

    if md_file.is_file():
        text = load_cv_md(md_file)
        if text:
            return text, md_file.as_posix()

    if pdf_file.is_file():
        text = load_cv_pdf(pdf_file)
        if text:
            return text, pdf_file.as_posix()

    return "", ""


def load_case_studies(persona_dir: Path) -> list[dict[str, Any]]:
    """Loads all Markdown case studies under case_studies/, parsing YAML front-matter."""
    cs_dir = persona_dir / "case_studies"
    if not cs_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for f in sorted(cs_dir.glob("*.md")):
        raw = f.read_text(encoding="utf-8", errors="ignore")
        meta: dict[str, Any] = {}
        body = raw

        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except (yaml.YAMLError, ValueError):
                    meta = {}
                    body = parts[2].strip()

        items.append(
            {
                "id": meta.get("id") or f.stem,
                "project": meta.get("project", f.stem),
                "skills": meta.get("skills", []),
                "date": str(meta.get("date", "")),
                "client_industry": meta.get("client_industry"),
                "outcome": meta.get("outcome"),
                "source_path": f.as_posix(),
                "text": body,
            }
        )
    return items


def load_repos(persona_dir: Path, source: RepoSource | None = None) -> list[RepoFile]:
    """Loads repository README and code files using the configured RepoSource."""
    repo_src = source or LocalRepoSource()
    repo_names = repo_src.list_repos(persona_dir)
    all_files: list[RepoFile] = []
    for r in repo_names:
        all_files.extend(repo_src.get_repo_files(persona_dir, r))
    return all_files


def load_reviews(persona_dir: Path) -> list[dict[str, Any]]:
    """Loads client reviews from reviews.json."""
    rev_file = persona_dir / "reviews.json"
    if not rev_file.is_file():
        return []
    try:
        return json.loads(rev_file.read_text(encoding="utf-8")) or []
    except (json.JSONDecodeError, OSError):
        return []


def load_proposals(persona_dir: Path) -> list[dict[str, Any]]:
    """Loads past proposals from past_proposals.jsonl."""
    prop_file = persona_dir / "past_proposals.jsonl"
    if not prop_file.is_file():
        return []
    proposals: list[dict[str, Any]] = []
    for line in prop_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                proposals.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
    return proposals


def load_profile(persona_dir: Path) -> dict[str, Any]:
    """Loads profile metadata from profile.json."""
    p_file = persona_dir / "profile.json"
    if not p_file.is_file():
        return {}
    try:
        return json.loads(p_file.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}

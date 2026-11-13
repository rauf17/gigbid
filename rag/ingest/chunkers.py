"""Chunking strategies for persona evidence artifacts.

Implements:
- Prose chunking (~350 tokens, ~50 token overlap) for CVs and long prose.
- Structural / line-based chunking for repository code.
- Atomic chunking for compact case studies, reviews, and historical proposals.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rag.ingest.loaders import (
    load_case_studies,
    load_cv,
    load_profile,
    load_proposals,
    load_repos,
    load_reviews,
)
from rag.ingest.repo_source import RepoSource
from rag.schema import Chunk


def compute_content_hash(text: str) -> str:
    """Computes a deterministic SHA-256 hash of normalized chunk text."""
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_prose_text(text: str, chunk_size_words: int = 280, overlap_words: int = 40) -> list[str]:
    """Splits prose text into ~350 token chunks with ~50 token overlap."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_words: list[str] = []

    for para in paragraphs:
        words = para.split()
        while len(current_words) + len(words) > chunk_size_words:
            needed = chunk_size_words - len(current_words)
            if needed > 0:
                current_words.extend(words[:needed])
                words = words[needed:]
            chunks.append(" ".join(current_words))
            overlap = current_words[-overlap_words:] if len(current_words) > overlap_words else current_words
            current_words = list(overlap)

        if words:
            current_words.extend(words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks if chunks else [text.strip()]


def chunk_code_text(code: str, max_lines: int = 45, overlap_lines: int = 10) -> list[str]:
    """Splits source code into bounded line chunks preserving block context."""
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return [code.strip()] if code.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        chunk_str = "\n".join(lines[start:end]).strip()
        if chunk_str:
            chunks.append(chunk_str)
        if end >= len(lines):
            break
        start += max_lines - overlap_lines

    return chunks


chunk_prose = chunk_prose_text
chunk_code = chunk_code_text


def build_chunks_for_persona(
    persona_id: str,
    persona_dir: Path,
    repo_source: RepoSource | None = None,
) -> list[Chunk]:
    """Extracts, chunks, and attaches full metadata to all persona assets."""
    chunks: list[Chunk] = []
    profile = load_profile(persona_dir)
    profile_skills: list[str] = profile.get("skills", [])

    # 1. CV (cv.md / cv.pdf)
    cv_text, cv_path = load_cv(persona_dir)
    if cv_text:
        cv_chunks = chunk_prose_text(cv_text, chunk_size_words=260, overlap_words=40)
        for idx, text_block in enumerate(cv_chunks):
            cid = f"{persona_id}_cv_{idx:03d}"
            chunks.append(
                Chunk(
                    id=cid,
                    persona=persona_id,
                    type="cv",
                    project=None,
                    skills=profile_skills,
                    date=None,
                    client_industry=None,
                    outcome=None,
                    source_path=cv_path,
                    text=text_block,
                    content_hash=compute_content_hash(text_block),
                )
            )

    # 2. Case Studies (kept whole if short)
    case_studies = load_case_studies(persona_dir)
    for cs in case_studies:
        cid = f"{persona_id}_cs_{cs['id']}"
        text_body = cs["text"]
        chunks.append(
            Chunk(
                id=cid,
                persona=persona_id,
                type="case_study",
                project=cs.get("project"),
                skills=cs.get("skills", []),
                date=cs.get("date"),
                client_industry=cs.get("client_industry"),
                outcome=cs.get("outcome"),
                source_path=cs.get("source_path", ""),
                text=text_body,
                content_hash=compute_content_hash(text_body),
            )
        )

    # 3. Repositories (README + Code)
    repo_files = load_repos(persona_dir, source=repo_source)
    for rf in repo_files:
        src_path = f"repos/{rf.repo_name}/{rf.relative_path}"
        if rf.is_readme:
            # README chunking
            readme_blocks = chunk_prose_text(rf.content, chunk_size_words=300, overlap_words=50)
            for idx, blk in enumerate(readme_blocks):
                cid = f"{persona_id}_repo_{rf.repo_name}_readme_{idx:02d}"
                chunks.append(
                    Chunk(
                        id=cid,
                        persona=persona_id,
                        type="repo_readme",
                        project=rf.repo_name,
                        skills=profile_skills,
                        date=None,
                        client_industry=None,
                        outcome=None,
                        source_path=src_path,
                        text=blk,
                        content_hash=compute_content_hash(blk),
                    )
                )
        else:
            # Code chunking
            code_blocks = chunk_code_text(rf.content, max_lines=45, overlap_lines=10)
            for idx, blk in enumerate(code_blocks):
                sanitized_name = rf.relative_path.replace("/", "_").replace(".", "_")
                cid = f"{persona_id}_repo_{rf.repo_name}_{sanitized_name}_{idx:02d}"
                chunks.append(
                    Chunk(
                        id=cid,
                        persona=persona_id,
                        type="repo_code",
                        project=rf.repo_name,
                        skills=profile_skills,
                        date=None,
                        client_industry=None,
                        outcome=None,
                        source_path=src_path,
                        text=blk,
                        content_hash=compute_content_hash(blk),
                    )
                )

    # 4. Reviews (Atomic per review)
    reviews = load_reviews(persona_dir)
    for idx, rev in enumerate(reviews):
        rev_id = rev.get("review_id", f"rev_{idx:03d}")
        cid = f"{persona_id}_review_{rev_id}"
        rev_text = (
            f"Client Review for {rev.get('project_title', 'Project')}:\n"
            f"Client: {rev.get('client_name')} ({rev.get('client_industry')})\n"
            f"Rating: {rev.get('rating')}/5.0 | Spend: ${rev.get('amount_earned_usd')}\n"
            f"Feedback: {rev.get('feedback')}"
        )
        chunks.append(
            Chunk(
                id=cid,
                persona=persona_id,
                type="review",
                project=rev.get("project_title"),
                skills=profile_skills,
                date=rev.get("date"),
                client_industry=rev.get("client_industry"),
                outcome=None,
                source_path="reviews.json",
                text=rev_text,
                content_hash=compute_content_hash(rev_text),
            )
        )

    # 5. Past Proposals (Atomic per proposal)
    proposals = load_proposals(persona_dir)
    for prop in proposals:
        prop_id = prop.get("id") or compute_content_hash(prop.get("text", ""))[:12]
        cid = f"{persona_id}_prop_{prop_id}"
        prop_text = (
            f"Job Title: {prop.get('job_title')}\n"
            f"Outcome: {prop.get('outcome')}\n"
            f"Proposal Text:\n{prop.get('text')}"
        )
        chunks.append(
            Chunk(
                id=cid,
                persona=persona_id,
                type="proposal",
                project=prop.get("job_title"),
                skills=profile_skills,
                date=prop.get("date"),
                client_industry=None,
                outcome=prop.get("outcome"),
                source_path="past_proposals.jsonl",
                text=prop_text,
                content_hash=compute_content_hash(prop_text),
            )
        )

    return chunks

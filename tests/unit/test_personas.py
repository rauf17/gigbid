"""Unit tests for synthetic persona corpora (AI-4016 GigBid Phase 1a).

Validates schema, file counts, outcome correlation rules, and PDF validity.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pypdf
import yaml

PERSONAS = ["ai_ml", "fullstack", "data_analyst"]
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "personas"


def test_persona_directories_exist():
    assert DATA_DIR.exists(), f"Directory not found: {DATA_DIR}"
    for pid in PERSONAS:
        pdir = DATA_DIR / pid
        assert pdir.exists() and pdir.is_dir(), f"Persona dir missing: {pdir}"


def test_required_files_exist():
    for pid in PERSONAS:
        pdir = DATA_DIR / pid
        for fname in ["profile.json", "cv.md", "cv.pdf", "reviews.json", "past_proposals.jsonl"]:
            fpath = pdir / fname
            assert fpath.exists() and fpath.is_file(), f"Missing file: {fpath}"
            assert fpath.stat().st_size > 0, f"Empty file: {fpath}"
        assert (pdir / "case_studies").is_dir(), f"Missing case_studies dir in {pdir}"
        assert (pdir / "repos").is_dir(), f"Missing repos dir in {pdir}"


def test_profile_schema():
    required_keys = {
        "id", "name", "title", "hourly_rate", "floor_hourly_rate",
        "min_fixed_rate", "weekly_connects_budget", "filters", "skills",
        "bio", "education", "synthetic"
    }
    for pid in PERSONAS:
        profile_path = DATA_DIR / pid / "profile.json"
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        assert required_keys.issubset(data.keys()), f"Missing keys in {profile_path}"
        assert data["id"] == pid
        assert data["synthetic"] is True
        assert data["hourly_rate"] >= data["floor_hourly_rate"]
        assert data["weekly_connects_budget"] > 0
        assert isinstance(data["skills"], list) and len(data["skills"]) >= 5
        assert isinstance(data["filters"], dict)


def test_cv_and_pdf():
    for pid in PERSONAS:
        cv_md = (DATA_DIR / pid / "cv.md").read_text(encoding="utf-8")
        assert "SYNTHETIC" in cv_md
        assert len(cv_md.splitlines()) > 20

        pdf_path = DATA_DIR / pid / "cv.pdf"
        reader = pypdf.PdfReader(str(pdf_path))
        assert len(reader.pages) >= 1
        text = reader.pages[0].extract_text()
        assert len(text) > 50


def test_case_studies_count_and_frontmatter():
    for pid in PERSONAS:
        cs_files = list((DATA_DIR / pid / "case_studies").glob("*.md"))
        assert 15 <= len(cs_files) <= 25, f"Unexpected case studies count {len(cs_files)} in {pid}"

        for cs_file in cs_files:
            content = cs_file.read_text(encoding="utf-8")
            # Parse YAML frontmatter between ---
            match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
            assert match, f"Invalid frontmatter in {cs_file}"
            fm_text, body = match.group(1), match.group(2)
            fm = yaml.safe_load(fm_text)

            for key in ["id", "project", "skills", "date", "client_industry", "outcome", "synthetic"]:
                assert key in fm, f"Missing key {key} in frontmatter of {cs_file}"
            assert fm["synthetic"] is True
            assert isinstance(fm["skills"], list) and len(fm["skills"]) > 0
            assert len(fm["outcome"]) > 10
            assert len(body) > 100


def test_repos_structure():
    for pid in PERSONAS:
        repos_dir = DATA_DIR / pid / "repos"
        repos = [d for d in repos_dir.iterdir() if d.is_dir()]
        assert len(repos) >= 2, f"Expected at least 2 repos in {repos_dir}"

        for r in repos:
            readme = r / "README.md"
            assert readme.exists(), f"Missing README.md in {r}"
            code_files = [f for f in r.iterdir() if f.is_file() and f.name != "README.md"]
            assert 2 <= len(code_files) <= 4, f"Expected 2-4 code files in {r}, got {len(code_files)}"
            for cf in code_files:
                txt = cf.read_text(encoding="utf-8")
                assert "synthetic: true" in txt, f"Missing synthetic tag in {cf}"


def test_reviews():
    for pid in PERSONAS:
        rev_path = DATA_DIR / pid / "reviews.json"
        reviews = json.loads(rev_path.read_text(encoding="utf-8"))
        assert isinstance(reviews, list)
        assert len(reviews) >= 10, f"Expected >= 10 reviews in {rev_path}"

        for r in reviews:
            for key in ["review_id", "client_name", "client_industry", "project_title", "rating", "feedback", "date", "synthetic"]:
                assert key in r, f"Missing key {key} in review: {r}"
            assert r["synthetic"] is True
            assert 4.0 <= r["rating"] <= 5.0


def test_past_proposals_counts_and_outcome_rules():
    for pid in PERSONAS:
        proposals_path = DATA_DIR / pid / "past_proposals.jsonl"
        lines = proposals_path.read_text(encoding="utf-8").strip().splitlines()
        assert 140 <= len(lines) <= 160, f"Expected ~150 proposals, got {len(lines)} in {pid}"

        proposals = [json.loads(l) for l in lines]
        won = [p for p in proposals if p["outcome"] == "won"]
        replied = [p for p in proposals if p["outcome"] == "replied"]
        ignored = [p for p in proposals if p["outcome"] == "ignored"]

        assert len(won) > 20, f"Too few won proposals in {pid}"
        assert len(replied) > 20, f"Too few replied proposals in {pid}"
        assert len(ignored) > 20, f"Too few ignored proposals in {pid}"

        # Collect all case study outcome metrics
        cs_metrics = []
        for cs_file in (DATA_DIR / pid / "case_studies").glob("*.md"):
            content = cs_file.read_text(encoding="utf-8")
            match = re.search(r'outcome:\s*"([^"]+)"', content)
            if match:
                cs_metrics.append(match.group(1))

        assert len(cs_metrics) >= 15

        # 1. Won proposals must cite a specific project and metric from that persona's case studies
        for w in won:
            assert w["synthetic"] is True
            cites_metric = any(metric in w["text"] for metric in cs_metrics)
            assert cites_metric, f"Won proposal {w['id']} does not cite a case study metric: {w['text']}"

        # 2. Replied proposals cite skills but no metrics
        for r in replied:
            assert r["synthetic"] is True
            has_metric = any(metric in r["text"] for metric in cs_metrics)
            assert not has_metric, f"Replied proposal {r['id']} should not cite specific metrics: {r['text']}"

        # 3. Ignored proposals are generic openers without metrics
        for ig in ignored:
            assert ig["synthetic"] is True
            has_metric = any(metric in ig["text"] for metric in cs_metrics)
            assert not has_metric, f"Ignored proposal {ig['id']} should not cite specific metrics: {ig['text']}"

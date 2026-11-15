"""Repo rules the assignment says CI must enforce.
1. no secrets in repo   2. nothing under gigsim/ changed (hash lock)
3. every prompt lives in agent/prompts/ (no long inline strings in agent/)
4. no hidden test set committed   (5. README numbers -> evals/results: added in Phase 5)
"""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
fails: list[str] = []

def tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], check=False, cwd=ROOT, capture_output=True, text=True
    ).stdout
    return [ROOT / l for l in out.splitlines() if (ROOT / l).is_file()]

SECRET_PATTERNS = [r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{30,}",
                   r"xox[bap]-[A-Za-z0-9-]{10,}", r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
                   r"gsk_[A-Za-z0-9]{20,}", r"lsv2_[A-Za-z0-9_]{20,}"]
files = tracked()
for f in files:
    rel = f.relative_to(ROOT).as_posix()
    if rel == ".env" or (rel.startswith(".env") and rel != ".env.example"):
        fails.append(f"secret file tracked: {rel}")
    if f.suffix in {".png", ".pdf", ".lock", ".sha256"} or "node_modules" in rel:
        continue
    try:
        txt = f.read_text(errors="ignore")
    except OSError:
        continue
    for pat in SECRET_PATTERNS:
        if re.search(pat, txt):
            fails.append(f"possible secret in {rel} (pattern {pat})")

# gigsim lock
lock = ROOT / "gigsim" / ".lock.sha256"
def gigsim_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(
        (ROOT / "gigsim").rglob("*"),
        key=lambda p: PurePosixPath(p.relative_to(ROOT).as_posix()),
    ):
        if (
            p.is_file()
            and p.name not in {".lock.sha256", ".gitkeep"}
            and "__pycache__" not in p.parts
            and "state" not in p.parts
        ):
            h.update(p.relative_to(ROOT).as_posix().encode())
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()
if lock.exists():
    if lock.read_text().strip() != gigsim_hash():
        fails.append("gigsim/ changed since it was frozen (.lock.sha256 mismatch)")
else:
    print("note: gigsim/.lock.sha256 not created yet (freeze it after Phase 1)")

# inline prompts
for f in (ROOT / "agent").rglob("*.py"):
    try:
        tree = ast.parse(f.read_text())
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and len(n.value) > 300
            and n is not (tree.body[0].value if tree.body and isinstance(tree.body[0], ast.Expr) else None)
        ):
            fails.append(f"long inline string (prompt?) in {f.relative_to(ROOT)}:{n.lineno}")

# hidden set
for f in files:
    rel = f.relative_to(ROOT).as_posix()
    if rel.startswith("evals/datasets/") and re.search(r"hidden|test_set", rel):
        fails.append(f"hidden/test set committed: {rel}")

# hardcoded model names in code (R8)
MODEL_NAME_PATTERN = re.compile(r"gpt-oss|qwen|llama|gemini|claude|gpt-4", re.IGNORECASE)
for f in files:
    rel = f.relative_to(ROOT).as_posix()
    if not rel.endswith(".py"):
        continue
    if (
        rel == "agent/llm.py"
        or rel == "scripts/check_repo_rules.py"
        or rel.startswith(("tests/", "data/"))
    ):
        continue
    try:
        txt = f.read_text(errors="ignore")
    except OSError:
        continue
    match = MODEL_NAME_PATTERN.search(txt)
    if match:
        fails.append(
            f"hardcoded model name '{match.group(0)}' in {rel} (must be configured in agent/config.yaml)"
        )

# 5. README results numbers -> docs/results_index.md
readme_path = ROOT / "README.md"
index_path = ROOT / "docs" / "results_index.md"
if readme_path.is_file() and index_path.is_file():
    readme_text = readme_path.read_text(encoding="utf-8")
    index_text = index_path.read_text(encoding="utf-8")
    res_match = re.search(r"## Results\s*\n(.*?)(?=\n## |\Z)", readme_text, re.DOTALL)
    if res_match:
        section = res_match.group(1)
        claims = re.findall(r"\b\d+(?:\.\d+)?%?", section)
        for claim in claims:
            clean_num = claim.rstrip("%")
            if claim not in index_text and clean_num not in index_text:
                fails.append(
                    f"number claim '{claim}' in README.md ## Results not listed in docs/results_index.md"
                )

if fails:
    print("REPO RULE FAILURES:"); [print(" -", x) for x in fails]; sys.exit(1)
print("repo rules OK")

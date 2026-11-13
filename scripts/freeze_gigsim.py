"""Freeze script for gigsim/ module (AI-4016 GigBid Phase 1b Part 5).

Writes gigsim/.lock.sha256 using the EXACT hashing algorithm from scripts/check_repo_rules.py.
DO NOT RUN AUTOMATICALLY during development - run only after manual review of Phase 1.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def gigsim_hash() -> str:
    """Computes SHA-256 over all non-ignored files under gigsim/."""
    h = hashlib.sha256()
    for p in sorted((ROOT / "gigsim").rglob("*")):
        if p.is_file() and p.name not in {".lock.sha256", ".gitkeep"} and "__pycache__" not in p.parts:
            h.update(p.relative_to(ROOT).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def freeze() -> None:
    """Writes the current gigsim hash to gigsim/.lock.sha256."""
    digest = gigsim_hash()
    lock_file = ROOT / "gigsim" / ".lock.sha256"
    lock_file.write_text(digest + "\n", encoding="utf-8")
    print(f"Frozen gigsim/ with hash {digest} -> {lock_file}")


if __name__ == "__main__":
    freeze()

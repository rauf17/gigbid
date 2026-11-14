"""Optional smoke script for real Groq LLM API invocation (Requirement R8).

Usage:
    GROQ_API_KEY=gsk_... uv run python scripts/llm_smoke.py

Skipped cleanly if GROQ_API_KEY is not set. Never run in CI.
"""
from __future__ import annotations

import os
import sys
import time

from agent.llm import get_active_profile, get_llm, llm_call


def main() -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[llm_smoke] NOTICE: GROQ_API_KEY not set. Skipping live Groq smoke test.")
        sys.exit(0)

    profile = get_active_profile()
    node = "analyst"
    print(f"[llm_smoke] Running live smoke test for node '{node}' under profile '{profile}'...")

    try:
        model = get_llm(node=node)
        model_name = getattr(model, "model_name", "unknown")
        print(f"[llm_smoke] Resolved Model: {model_name}")

        t0 = time.time()
        res = llm_call(
            node=node,
            variables={
                "job_post": "Need a Python developer to build a FastAPI endpoint with PostgreSQL.",
                "persona": "Full-Stack Web Developer",
            },
        )
        latency_ms = (time.time() - t0) * 1000.0

        content = str(getattr(res, "content", res))
        print(f"[llm_smoke] SUCCESS ({latency_ms:.1f}ms):")
        print(f"[llm_smoke] Response snippet: {content[:150]}...")
    except Exception as exc:  # noqa: BLE001
        print(f"[llm_smoke] ERROR during live LLM invocation: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

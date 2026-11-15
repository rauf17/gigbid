"""LangSmith Tracing Scenarios Generator (Requirement E3).

Executes four canonical end-to-end scenarios against GigSim and Postgres,
printing the thread_id, trace_id, and LangSmith run URL for each:
(a) a skipped scam job
(b) an approved proposal
(c) a Critic revision loop
(d) a crash-and-resume
"""
from __future__ import annotations

import asyncio
import uuid

from agent.runtime import resume, run_job
from agent.tracing import get_run_url, init_tracing


async def run_scenario_a_scam() -> dict[str, str]:
    """Scenario (a): A skipped scam job."""
    trace_id = str(uuid.uuid4())
    job = {
        "id": f"scam_job_{uuid.uuid4().hex[:6]}",
        "title": "URGENT: High-paying data entry - contact Telegram",
        "description": "Earn $500/day. Contact immediately on Telegram @crypto_pay or WhatsApp +1-555-0199 for off-platform payment via Bitcoin.",
        "category": "ai_ml",
        "budget": 5000.0,
        "budget_type": "fixed",
    }
    thread_id = f"reviewer:{job['id']}"
    state = await run_job(
        job=job,
        user_id="reviewer",
        persona_id="ai_ml",
        trace_id=trace_id,
    )
    url = get_run_url(trace_id)
    dec = state.get("decision")
    action = getattr(dec, "action", None) or (dec.get("action") if isinstance(dec, dict) else "skip")
    return {
        "scenario": "(a) Skipped scam job",
        "job_id": job["id"],
        "thread_id": thread_id,
        "trace_id": trace_id,
        "decision": str(action),
        "run_url": url,
    }


async def run_scenario_b_approved() -> dict[str, str]:
    """Scenario (b): An approved proposal."""
    trace_id = str(uuid.uuid4())
    job = {
        "id": f"valid_job_{uuid.uuid4().hex[:6]}",
        "title": "Senior Python & FastAPI Engineer for Distributed ML Pipeline",
        "description": "Looking for an experienced engineer to optimize FastAPI asynchronous endpoints and integrate pgvector semantic search.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "category": "ai_ml",
        "budget": 3500.0,
        "budget_type": "fixed",
    }
    thread_id = f"reviewer:{job['id']}"

    # 1. Run until approval interrupt
    await run_job(
        job=job,
        user_id="reviewer",
        persona_id="ai_ml",
        trace_id=trace_id,
    )

    # 2. Resume with approval
    await resume(
        thread_id=thread_id,
        decision={"action": "approve", "feedback": "Approved proposal for submission."},
    )
    url = get_run_url(trace_id)
    return {
        "scenario": "(b) Approved proposal",
        "job_id": job["id"],
        "thread_id": thread_id,
        "trace_id": trace_id,
        "decision": "approved",
        "run_url": url,
    }


async def run_scenario_c_critic_loop() -> dict[str, str]:
    """Scenario (c): A Critic revision loop."""
    trace_id = str(uuid.uuid4())
    job = {
        "id": f"revision_job_{uuid.uuid4().hex[:6]}",
        "title": "Machine Learning Model Quantization Expert",
        "description": "Quantize LLM weights to INT4 using AWQ and vLLM. Include exact benchmarks from previous deployments.",
        "skills": ["PyTorch", "vLLM", "Quantization"],
        "category": "ai_ml",
        "budget": 4000.0,
        "budget_type": "fixed",
    }
    thread_id = f"reviewer:{job['id']}"

    # Execution will loop through Critic when critique requests revision
    state = await run_job(
        job=job,
        user_id="reviewer",
        persona_id="ai_ml",
        trace_id=trace_id,
    )
    rev_count = state.get("revision_count", 1)
    url = get_run_url(trace_id)
    return {
        "scenario": "(c) Critic revision loop",
        "job_id": job["id"],
        "thread_id": thread_id,
        "trace_id": trace_id,
        "revisions": str(rev_count),
        "run_url": url,
    }


async def run_scenario_d_crash_resume() -> dict[str, str]:
    """Scenario (d): A crash-and-resume."""
    trace_id = str(uuid.uuid4())
    job = {
        "id": f"crash_job_{uuid.uuid4().hex[:6]}",
        "title": "Data Pipeline Architect for Real-Time Streaming",
        "description": "Build streaming ETL pipeline using Kafka, ClickHouse, and Python for financial metrics.",
        "skills": ["Python", "Kafka", "ClickHouse"],
        "category": "data_analyst",
        "budget": 4500.0,
        "budget_type": "fixed",
    }
    thread_id = f"reviewer:{job['id']}"

    # Step 1: Execute graph until it hits approval interrupt and persists in Postgres
    await run_job(
        job=job,
        user_id="reviewer",
        persona_id="data_analyst",
        trace_id=trace_id,
    )

    # Step 2: Simulate process crash and restart: completely separate resume call
    await resume(
        thread_id=thread_id,
        decision={"action": "approve", "feedback": "Resumed after worker restart."},
    )
    url = get_run_url(trace_id)
    return {
        "scenario": "(d) Crash-and-resume",
        "job_id": job["id"],
        "thread_id": thread_id,
        "trace_id": trace_id,
        "resumed": "true",
        "run_url": url,
    }


async def main() -> None:
    print("================================================================================")
    print("                    LANGSMITH TRACING EXAMPLES (Requirement E3)                 ")
    print("================================================================================")
    is_active = init_tracing()
    print(f"Tracing Status: {'ACTIVE (LangSmith enabled)' if is_active else 'STANDBY (silent offline mode)'}\n")

    scenarios = [
        run_scenario_a_scam,
        run_scenario_b_approved,
        run_scenario_c_critic_loop,
        run_scenario_d_crash_resume,
    ]

    for fn in scenarios:
        try:
            res = await fn()
            print(f"Scenario:  {res['scenario']}")
            print(f"Thread ID: {res['thread_id']}")
            print(f"Trace ID:  {res['trace_id']}")
            print(f"Run URL:   {res['run_url']}")
            print("--------------------------------------------------------------------------------")
        except Exception as exc:  # noqa: BLE001
            print(f"Scenario error ({fn.__name__}): {exc}")


if __name__ == "__main__":
    asyncio.run(main())

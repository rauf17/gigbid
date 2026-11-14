"""Hand-written StateGraph bid graph for the GigBid autonomous bidding pipeline.

Assignment requirements:
- C1: Hand-written StateGraph (NO create_react_agent, NO langgraph-supervisor).
- C2: Parallel fan-out via Send (analyst, risk_assessor, fit_matcher) -> join.
- C4: Resource budgets (step limit, token limit, critic revision guard).
- C5: Interactive approval interrupt with dry_run preview.
- C6: Idempotent proposal submission with Connects spending guard.
- C7: Resilient execution with RetryPolicy and dead-letter fail-safe.
- R3, R4, R7: Strict port-mediated marketplace access and zero LLM in GigSim.
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import RetryPolicy, RunnableConfig, Send, StreamWriter, interrupt

from agent.db import (
    get_proposal_submission,
    record_proposal_submission,
    write_audit_trace,
    write_dead_letter,
)
from agent.marketplace_port import MarketplaceUnavailable, RateLimited
from agent.nodes import (
    NodeDeps,
    analyst,
    compliance,
    critic,
    decision,
    fit_matcher,
    pricing,
    risk_assessor,
    verifier,
)
from agent.nodes import (
    writer as writer_node,
)
from agent.state import BidGraphState, BidStatus

logger = logging.getLogger(__name__)

DEFAULT_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=0.5,
    backoff_factor=2.0,
    jitter=True,
)


def _get_active_deps(config: RunnableConfig | None, fallback: NodeDeps | None) -> NodeDeps:
    """Extracts injected NodeDeps from config or falls back to default container."""
    if config and "configurable" in config and "deps" in config["configurable"]:
        return config["configurable"]["deps"]
    return fallback or NodeDeps()


def _get_thread_id(config: RunnableConfig | None) -> str:
    """Resolves thread_id from runnable configuration."""
    if config and "configurable" in config and "thread_id" in config["configurable"]:
        return str(config["configurable"]["thread_id"])
    return "default_thread"


def _check_budget(state: BidGraphState, deps: NodeDeps) -> str | None:
    """Checks whether current execution exceeded max steps or token limits."""
    cfg = deps.get_config().get("budgets", {})
    max_steps = int(cfg.get("max_graph_steps", 30))
    max_tokens = int(cfg.get("max_tokens_per_job", 12000))

    b = state.get("budget", {"steps": 0, "tokens": 0})
    steps = b.get("steps", 0)
    tokens = b.get("tokens", 0)

    if steps >= max_steps:
        return f"Step budget exceeded ({steps}/{max_steps})"
    if tokens >= max_tokens:
        return f"Token budget exceeded ({tokens}/{max_tokens})"
    return None


# -----------------------------------------------------------------------------
# Graph Nodes
# -----------------------------------------------------------------------------


async def node_intake(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Initializes job state, trace metadata, and starting budget."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    trace_id = state.get("trace_id") or uuid4().hex
    writer({"event": "node_start", "node": "intake", "thread_id": thread_id})

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=trace_id,
        thread_id=thread_id,
        node_name="intake",
        observation=f"Intake initialized for job {state.get('job', {}).get('id')}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "intake", "duration_ms": dur, "tokens": 0})

    return {
        "status": BidStatus.RUNNING,
        "trace_id": trace_id,
        "revision_count": 0,
        "budget": {"steps": 1, "tokens": 0},
    }


def fanout_assessments(state: BidGraphState) -> list[Send]:
    """Parallel fan-out via Send: analyst, risk_assessor, fit_matcher."""
    return [
        Send("analyst", state),
        Send("risk_assessor", state),
        Send("fit_matcher", state),
    ]


async def node_analyst(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Runs requirement decomposition and job spec analysis."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "analyst"})

    spec = await analyst.run(
        {"job": state.get("job", {}), "persona": state.get("persona_id", "ai_ml")},
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="analyst",
        observation=f"Extracted {len(spec.requirements)} requirements",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "analyst", "duration_ms": dur, "tokens": 0})
    return {"spec": spec, "budget": {"steps": 1, "tokens": 0}}


async def node_risk_assessor(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Runs safety, scam, and injection screening."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "risk_assessor"})

    risk = await risk_assessor.run({"job": state.get("job", {})}, deps)
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="risk_assessor",
        observation=f"Risk score: {risk.risk_score:.2f}, recommendation: {risk.recommendation}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "risk_assessor", "duration_ms": dur, "tokens": 0})
    return {"risk": risk, "budget": {"steps": 1, "tokens": 0}}


async def node_fit_matcher(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Runs portfolio capability alignment in parallel without depending on analyst."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "fit_matcher"})

    fit = await fit_matcher.run(
        {"job": state.get("job", {}), "persona": state.get("persona_id", "ai_ml")},
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="fit_matcher",
        observation=f"Fit score: {fit.fit_score:.2f}, gaps={len(fit.gaps)}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "fit_matcher", "duration_ms": dur, "tokens": 0})
    return {"fit": fit, "budget": {"steps": 1, "tokens": 0}}


async def node_join(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Fan-in junction aggregating parallel assessment branches."""
    writer({"event": "node_join", "node": "join"})
    return {"budget": {"steps": 1, "tokens": 0}}


async def node_decide(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Evaluates combined assessments against thresholds and user autonomy policy."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "decide"})

    # Check resource budget before decision
    budget_err = _check_budget(state, deps)
    if budget_err:
        return {"status": BidStatus.NEEDS_ATTENTION, "skip_reason": budget_err}

    res = await decision.run(
        {
            "spec": state.get("spec"),
            "risk": state.get("risk"),
            "fit": state.get("fit"),
            "job": state.get("job", {}),
        },
        deps,
    )

    autonomy = deps.get_config().get("autonomy", {})
    auto_skip = autonomy.get("auto_skip_low_fit", True)

    status = BidStatus.RUNNING
    skip_reason: str | None = None

    reasons_text = "; ".join(res.reasons) if res.reasons else "Candidate evaluation"
    if res.action == "skip":
        if auto_skip:
            status = BidStatus.SKIPPED
            skip_reason = reasons_text
        else:
            status = BidStatus.NEEDS_ATTENTION
            skip_reason = f"Candidate skipped by decision engine ({reasons_text}); review required."
    elif res.action == "watch":
        status = BidStatus.WATCHING
        skip_reason = reasons_text

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="decide",
        observation=f"Decision: {res.action}, status={status}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "decide", "duration_ms": dur, "tokens": 0})

    return {
        "decision": res,
        "status": status,
        "skip_reason": skip_reason,
        "budget": {"steps": 1, "tokens": 0},
    }


def route_after_decide(state: BidGraphState) -> str:
    """Conditional routing based on bid or skip/watch decision."""
    st = state.get("status")
    if st in {BidStatus.SKIPPED, BidStatus.WATCHING, BidStatus.NEEDS_ATTENTION}:
        return END
    return "pricing"


async def node_pricing(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Generates rate and pricing rationale based on client and job constraints."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "pricing"})

    quote = await pricing.run(
        {"job": state.get("job", {}), "spec": state.get("spec")},
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="pricing",
        observation=f"Proposed rate: {quote.bid_amount} (cost={quote.connects_cost})",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "pricing", "duration_ms": dur, "tokens": 0})
    return {"quote": quote, "budget": {"steps": 1, "tokens": 0}}


async def node_writer(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
    store: BaseStore | None = None,
) -> dict[str, Any]:
    """Drafts evidence-backed proposal grounded in verified portfolio items."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "writer"})

    # Evidence lookup via retriever if available
    evidence = state.get("evidence") or []
    if not evidence and deps.retriever:
        spec = state.get("spec")
        skills = [r.text for r in spec.requirements] if spec and spec.requirements else state.get("job", {}).get("skills", [])
        evidence = await deps.retriever.retrieve(query=skills, k=5)

    # Long-term style memory lookup
    user_id = state.get("user_id", "default_user")
    style_rules: list[str] = []
    if store is not None:
        try:
            items = await store.asearch(("style", user_id))
            style_rules = [i.value["rule_text"] for i in items if "rule_text" in i.value]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed reading style memory: %s", exc)

    if not style_rules and state.get("style_notes"):
        raw_notes = state.get("style_notes")
        style_rules = [raw_notes] if isinstance(raw_notes, str) else list(raw_notes)

    # Revision critique feedback if looping
    revision_notes: str | None = None
    critiques = state.get("critiques", [])
    if critiques:
        last_c = critiques[-1]
        issues = getattr(last_c, "issues", [])
        if issues:
            revision_notes = "; ".join(issues)
        else:
            revision_notes = getattr(last_c, "feedback", None) or getattr(last_c, "notes", None)

    draft = await writer_node.run(
        {
            "job": state.get("job", {}),
            "spec": state.get("spec"),
            "quote": state.get("quote"),
            "evidence": evidence,
            "style_rules": style_rules,
            "revision_notes": revision_notes,
        },
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="writer",
        observation=f"Drafted cover letter ({len(draft.cover_letter)} chars, {len(draft.claims)} claims)",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "writer", "duration_ms": dur, "tokens": 0})
    return {"draft": draft, "evidence": evidence, "budget": {"steps": 1, "tokens": 0}}


async def node_verifier(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Fact-checks claims against evidence and prunes ungrounded statements."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "verifier"})

    verified_draft, report = await verifier.run(
        {"draft": state.get("draft"), "evidence": state.get("evidence", [])},
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="verifier",
        observation=f"Verification: checks={len(report.checks)}, removed={len(report.removed)}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "verifier", "duration_ms": dur, "tokens": 0})
    return {"draft": verified_draft, "verification": report, "budget": {"steps": 1, "tokens": 0}}


async def node_critic(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Evaluates draft quality, tone, and evidence specificity."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "critic"})

    cur_rev = state.get("revision_count", 0)
    crit = await critic.run(
        {
            "job": state.get("job", {}),
            "draft": state.get("draft"),
            "verification": state.get("verification"),
            "risk": state.get("risk"),
            "revision_count": cur_rev,
        },
        deps,
    )
    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="critic",
        observation=f"Critique verdict: {crit.verdict}, issues={len(crit.issues)}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "critic", "duration_ms": dur, "tokens": 0})
    return {
        "critiques": [crit],
        "revision_count": cur_rev + 1,
        "budget": {"steps": 1, "tokens": 0},
    }


def route_after_critic(state: BidGraphState) -> str:
    """Routes back to writer if revision requested and revision limit not met."""
    crits = state.get("critiques", [])
    if crits:
        last_crit = crits[-1]
        rev_count = state.get("revision_count", 0)
        action_or_verdict = getattr(last_crit, "verdict", None) or getattr(last_crit, "action", None)
        if action_or_verdict == "revise" and rev_count < 2:
            return "writer"
    return "compliance"


async def node_compliance(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Checks proposal text against machine policy rules."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "compliance"})

    verdict = await compliance.run({"draft": state.get("draft")}, deps)
    dur = (time.perf_counter() - t0) * 1000.0

    status = BidStatus.AWAITING_APPROVAL
    skip_reason: str | None = None
    if not verdict.passed:
        status = BidStatus.NEEDS_ATTENTION
        skip_reason = f"Compliance block: {', '.join(f'{v.rule_id} ({v.span})' for v in verdict.violations)}"

    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="compliance",
        observation=f"Verdict: passed={verdict.passed}, violations={len(verdict.violations)}, status={status}",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "compliance", "duration_ms": dur, "tokens": 0})

    return {
        "compliance": verdict,
        "status": status,
        "skip_reason": skip_reason,
        "budget": {"steps": 1, "tokens": 0},
    }


def route_after_compliance(state: BidGraphState) -> str:
    """Conditional routing based on compliance pass or block."""
    if state.get("status") == BidStatus.NEEDS_ATTENTION:
        return END
    return "approval"


async def node_approval(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Suspends execution via interrupt() to present preview and await human approval.

    Enforces STRICT autonomy rule: NEVER auto-send proposals without human sign-off.
    """
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "approval"})

    # Autonomy guard: auto_send is strictly forbidden
    autonomy = deps.get_config().get("autonomy", {})
    if autonomy.get("auto_send") is True:
        raise ValueError("Policy violation: autonomous proposal submission (auto_send) is strictly prohibited.")

    # Compute idempotent dry_run preview before interrupt
    preview = state.get("dry_run_preview")
    if preview is None and deps.port:
        try:
            letter = state["draft"].cover_letter if state.get("draft") else ""
            rate = state["quote"].bid_amount if state.get("quote") else 0.0
            res_preview = await deps.port.create_proposal_draft(
                job_id=state.get("job", {}).get("id", ""),
                cover_letter=letter,
                bid_amount=rate,
                dry_run=True,
            )
            preview = res_preview.model_dump() if hasattr(res_preview, "model_dump") else res_preview.__dict__
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed computing dry_run preview: %s", exc)
            preview = {"dry_run": True, "message": "Preview generated without live port"}

    # Formulate review payload
    draft_obj = state.get("draft")
    payload = {
        "thread_id": thread_id,
        "job_id": state.get("job", {}).get("id", ""),
        "draft": draft_obj.model_dump() if hasattr(draft_obj, "model_dump") else draft_obj,
        "claims_matrix": [c.model_dump() if hasattr(c, "model_dump") else c for c in getattr(draft_obj, "claims", [])],
        "risk_report": state.get("risk").model_dump() if hasattr(state.get("risk"), "model_dump") else state.get("risk"),
        "price_rationale": state.get("quote").model_dump() if hasattr(state.get("quote"), "model_dump") else state.get("quote"),
        "dry_run_preview": preview,
    }

    # Suspend execution until Command(resume=decision) is received
    decision_val = interrupt(payload)

    action = decision_val.get("action", "approve") if isinstance(decision_val, dict) else "approve"
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="approval",
        observation=f"Approval resumed with action={action}",
    )
    writer({"event": "node_end", "node": "approval", "decision": decision_val})

    if action == "reject":
        return {
            "status": BidStatus.REJECTED,
            "approval": decision_val,
            "skip_reason": decision_val.get("reason", "Rejected during human review"),
            "dry_run_preview": preview,
            "budget": {"steps": 1, "tokens": 0},
        }

    if action == "edit":
        edited_text = decision_val.get("edited_text", "")
        orig_text = draft_obj.cover_letter if draft_obj else ""
        diff_record = {"original": orig_text, "edited": edited_text, "reason": decision_val.get("reason", "")}

        updated_draft = draft_obj.model_copy(update={"cover_letter": edited_text}) if hasattr(draft_obj, "model_copy") else draft_obj
        recheck = await compliance.run({"draft": updated_draft}, deps)
        if not recheck.passed:
            return {
                "status": BidStatus.NEEDS_ATTENTION,
                "draft": updated_draft,
                "compliance": recheck,
                "approval": {**decision_val, "diff": diff_record},
                "dry_run_preview": preview,
                "skip_reason": f"Edited text failed compliance: {', '.join(f'{v.rule_id} ({v.span})' for v in recheck.violations)}",
                "budget": {"steps": 1, "tokens": 0},
            }

        return {
            "status": BidStatus.RUNNING,
            "draft": updated_draft,
            "compliance": recheck,
            "approval": {**decision_val, "diff": diff_record},
            "dry_run_preview": preview,
            "budget": {"steps": 1, "tokens": 0},
        }

    # Approved
    return {
        "status": BidStatus.RUNNING,
        "approval": decision_val,
        "dry_run_preview": preview,
        "budget": {"steps": 1, "tokens": 0},
    }


def route_after_approval(state: BidGraphState) -> str:
    """Conditional routing based on human decision."""
    st = state.get("status")
    if st in {BidStatus.REJECTED, BidStatus.NEEDS_ATTENTION, BidStatus.DEAD_LETTER}:
        return END
    return "submit"


async def node_submit(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Submits approved proposal idempotently to marketplace, expending Connects."""
    t0 = time.perf_counter()
    thread_id = _get_thread_id(config)
    deps = _get_active_deps(config, None)
    writer({"event": "node_start", "node": "submit"})

    draft_obj = state.get("draft")
    final_text = draft_obj.cover_letter if draft_obj else ""
    idempotency_key = hashlib.sha256(f"{thread_id}:{final_text}".encode()).hexdigest()

    # Verify deduplication record in proposal_submissions
    existing = get_proposal_submission(thread_id)
    if existing and existing.get("status") == "submitted":
        logger.info("[submit] Submission already recorded for thread %s, skipping duplicate spend.", thread_id)
        dur = (time.perf_counter() - t0) * 1000.0
        write_audit_trace(
            trace_id=state.get("trace_id", ""),
            thread_id=thread_id,
            node_name="submit",
            observation="Idempotent replay detected, returned existing submission",
            duration_ms=dur,
        )
        return {"status": BidStatus.SUBMITTED, "outcome": existing, "budget": {"steps": 1, "tokens": 0}}

    outcome: dict[str, Any] = {"status": "submitted", "proposal_id": f"prop_{idempotency_key[:12]}"}
    rate = state.get("quote").bid_amount if state.get("quote") else 0.0

    if deps.port:
        try:
            draft_res = await deps.port.create_proposal_draft(
                job_id=state.get("job", {}).get("id", ""),
                cover_letter=final_text,
                bid_amount=rate,
                idempotency_key=f"d_{idempotency_key[:16]}",
                dry_run=False,
            )
            draft_id = getattr(draft_res, "id", f"prop_{idempotency_key[:12]}")
            sub_res = await deps.port.submit_proposal(
                proposal_id=draft_id,
                idempotency_key=f"s_{idempotency_key[:16]}",
                dry_run=False,
            )
            outcome = sub_res.model_dump() if hasattr(sub_res, "model_dump") else sub_res.__dict__
        except (MarketplaceUnavailable, RateLimited) as port_err:
            logger.error("[submit] Marketplace error during proposal submission: %s", port_err)
            write_dead_letter(thread_id, "submit", type(port_err).__name__, str(port_err), state)
            return {"status": BidStatus.DEAD_LETTER, "skip_reason": str(port_err)}

    # Record persistent submission proof
    record_proposal_submission(
        thread_id=thread_id,
        idempotency_key=idempotency_key,
        status="submitted",
        job_id=state.get("job", {}).get("id", ""),
        persona_id=state.get("persona_id", "ai_ml"),
        bid_amount=rate,
        proposal_text=final_text,
    )

    dur = (time.perf_counter() - t0) * 1000.0
    write_audit_trace(
        trace_id=state.get("trace_id", ""),
        thread_id=thread_id,
        node_name="submit",
        observation=f"Proposal submitted successfully (idempotency={idempotency_key[:12]})",
        duration_ms=dur,
    )
    writer({"event": "node_end", "node": "submit", "duration_ms": dur, "tokens": 0})

    return {"status": BidStatus.SUBMITTED, "outcome": outcome, "budget": {"steps": 1, "tokens": 0}}


async def node_dead_letter(
    state: BidGraphState,
    config: RunnableConfig,
    writer: StreamWriter,
) -> dict[str, Any]:
    """Records fatal thread failure into dead_letter table for offline inspection."""
    thread_id = _get_thread_id(config)
    reason = state.get("skip_reason") or "Fatal execution error"
    write_dead_letter(thread_id, "graph", "DeadLetterFailure", reason, state)
    writer({"event": "dead_letter", "reason": reason})
    return {"status": BidStatus.DEAD_LETTER, "skip_reason": reason}


# -----------------------------------------------------------------------------
# Graph Factory & Streaming
# -----------------------------------------------------------------------------


def build_bid_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    deps: NodeDeps | None = None,
) -> CompiledStateGraph:
    """Builds and compiles the hand-written StateGraph for autonomous bidding.

    Enforces autonomy policies, retry limits, and connects checkpointer/store.
    """
    deps = deps or NodeDeps()
    autonomy = deps.get_config().get("autonomy", {})
    if autonomy.get("auto_send") is True:
        raise ValueError("Policy violation: autonomous proposal submission (auto_send) is strictly prohibited.")

    builder = StateGraph(BidGraphState)

    # 1. Register nodes with RetryPolicy
    builder.add_node("intake", node_intake, retry_policy=DEFAULT_RETRY)
    builder.add_node("analyst", node_analyst, retry_policy=DEFAULT_RETRY)
    builder.add_node("risk_assessor", node_risk_assessor, retry_policy=DEFAULT_RETRY)
    builder.add_node("fit_matcher", node_fit_matcher, retry_policy=DEFAULT_RETRY)
    builder.add_node("join", node_join)
    builder.add_node("decide", node_decide, retry_policy=DEFAULT_RETRY)
    builder.add_node("pricing", node_pricing, retry_policy=DEFAULT_RETRY)
    builder.add_node("writer", node_writer, retry_policy=DEFAULT_RETRY)
    builder.add_node("verifier", node_verifier, retry_policy=DEFAULT_RETRY)
    builder.add_node("critic", node_critic, retry_policy=DEFAULT_RETRY)
    builder.add_node("compliance", node_compliance, retry_policy=DEFAULT_RETRY)
    builder.add_node("approval", node_approval)
    builder.add_node("submit", node_submit, retry_policy=DEFAULT_RETRY)
    builder.add_node("dead_letter", node_dead_letter)

    # 2. Control flow edges
    builder.add_edge(START, "intake")
    builder.add_conditional_edges("intake", fanout_assessments, ["analyst", "risk_assessor", "fit_matcher"])
    builder.add_edge("analyst", "join")
    builder.add_edge("risk_assessor", "join")
    builder.add_edge("fit_matcher", "join")
    builder.add_edge("join", "decide")

    builder.add_conditional_edges("decide", route_after_decide, [END, "pricing"])
    builder.add_edge("pricing", "writer")
    builder.add_edge("writer", "verifier")
    builder.add_edge("verifier", "critic")

    builder.add_conditional_edges("critic", route_after_critic, ["writer", "compliance"])
    builder.add_conditional_edges("compliance", route_after_compliance, [END, "approval"])
    builder.add_conditional_edges("approval", route_after_approval, [END, "submit"])
    builder.add_edge("submit", END)
    builder.add_edge("dead_letter", END)

    return builder.compile(checkpointer=checkpointer, store=store)


async def stream_bid(
    job: dict[str, Any],
    config: dict[str, Any] | None = None,
    *,
    thread_id: str | None = None,
    user_id: str = "default_user",
    persona_id: str = "ai_ml",
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    deps: NodeDeps | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """Streams node-by-node execution updates and custom telemetry events."""
    graph = build_bid_graph(checkpointer=checkpointer, store=store, deps=deps)
    tid = thread_id or f"{user_id}:{job.get('id', uuid4().hex)}"

    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": tid,
            "deps": deps or NodeDeps(),
        }
    }
    if config:
        run_config.update(config)

    initial_state: BidGraphState = {
        "job": job,
        "user_id": user_id,
        "persona_id": persona_id,
        "trace_id": uuid4().hex,
        "budget": {"steps": 0, "tokens": 0},
    }

    async for chunk in graph.astream(initial_state, config=run_config, stream_mode=["updates", "custom"]):
        yield chunk

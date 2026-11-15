"""Unit tests for the Change-Request Drill (Prompt 14 Part 2).

Proves that compliance and decision nodes change behavior solely from YAML edits
(data/policy_pack/policy.yaml and agent/config.yaml) with ZERO Python code changes.
"""
from __future__ import annotations

import pytest

from agent.handoffs import JobSpec, RiskReport
from agent.nodes import compliance, decision
from agent.nodes.base import NodeDeps


@pytest.mark.asyncio
async def test_change_request_new_banned_phrases() -> None:
    """Verifies that new banned phrases added to policy.yaml are actively flagged."""
    deps = NodeDeps()

    # Phrase 1: "guaranteed turnaround"
    draft_1 = "We will deliver this project with a guaranteed turnaround and clean test coverage."
    verdict_1 = await compliance.run({"proposal_draft": draft_1}, deps)
    rule_ids_1 = {v.rule_id for v in verdict_1.violations}
    assert "POL-006-GENERIC-SPAM-PHRASING" in rule_ids_1
    assert any("guaranteed turnaround" in v.span.lower() for v in verdict_1.violations)

    # Phrase 2: "best price guaranteed"
    draft_2 = "Choose us for this milestone: we offer the best price guaranteed for fullstack development."
    verdict_2 = await compliance.run({"proposal_draft": draft_2}, deps)
    rule_ids_2 = {v.rule_id for v in verdict_2.violations}
    assert "POL-006-GENERIC-SPAM-PHRASING" in rule_ids_2
    assert any("best price guaranteed" in v.span.lower() for v in verdict_2.violations)


@pytest.mark.asyncio
async def test_change_request_reduced_proposal_length_limit() -> None:
    """Verifies that lowering max_proposal_length from 2500 to 1800 triggers length violation."""
    deps = NodeDeps()
    # Construct a draft with 2000 characters (would pass 2500 chars, fails 1800 chars)
    long_draft = "Production engineering deliverable summary. " * 45  # ~1980 chars

    verdict = await compliance.run({"proposal_draft": long_draft}, deps)
    rule_ids = {v.rule_id for v in verdict.violations}
    assert "POL-007-PROPOSAL-LENGTH-LIMIT" in rule_ids


@pytest.mark.asyncio
async def test_change_request_higher_fit_threshold_skips_intermediate_jobs() -> None:
    """Verifies that increasing minimum_fit_score from 0.60 to 0.75 in config.yaml flips decision from bid to skip."""
    deps = NodeDeps()  # Loads live config.yaml with minimum_fit_score = 0.75

    spec = JobSpec(
        title="Backend Microservice Engineer",
        summary="Build scalable REST API with Postgres.",
        skills=["Python", "FastAPI", "PostgreSQL"],
        budget_min=2000.0,
        budget_max=4000.0,
    )
    risk = RiskReport(
        risk_score=0.20,
        flags=[],
        rationale="Client is verified with clean payment history.",
        recommendation="ok",
    )

    # An opportunity with fit_score = 0.68 (passes old 0.60 threshold, fails new 0.75 threshold)
    fit_report = {
        "fit_score": 0.68,
        "matrix": [],
        "gaps": [],
        "reasons": ["Good skill overlap with minor gaps."],
    }

    state = {
        "job_spec": spec,
        "risk_report": risk,
        "fit_report": fit_report,
        "job": {"id": "job_cr_test", "connects_cost": 8},
    }

    dec = await decision.run(state, deps)
    # Must now be SKIP due to new 0.75 threshold
    assert dec.action == "skip"
    assert any("0.75" in r or "Fit score" in r for r in dec.reasons)

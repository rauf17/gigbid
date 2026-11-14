"""Risk Assessor agent node: deterministic safety rules + client history + LLM judgment."""
from __future__ import annotations

import logging
import re
from typing import Any

from agent.handoffs import RiskFlag, RiskReport
from agent.llm import llm_call
from agent.nodes.base import NodeDeps

logger = logging.getLogger(__name__)


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> RiskReport:
    """Evaluates safety and risk of a job posting and its client history."""
    raw_job = state_slice.get("job") or {}
    if hasattr(raw_job, "model_dump"):
        job = raw_job.model_dump()
    elif isinstance(raw_job, dict):
        job = raw_job
    else:
        job = {"description": str(raw_job)}

    title = job.get("title", "")
    description = job.get("description", "")
    client_id = job.get("client_id")
    job_text = f"{title}\n\n{description}"

    policy = deps.get_policy()

    # 1. Deterministic Rule Matching (FIRST)
    det_flags: list[RiskFlag] = []
    det_evidence: list[str] = []
    det_score: float = 0.0
    hard_block = False

    # Check policy regex rules
    rule_matches = policy.match_regex_rules(job_text)
    for rule, pattern, m in rule_matches:
        span_text = m.group(0)
        det_evidence.append(f"[{rule.id}] Matched '{span_text}' via pattern '{pattern}'")

        if rule.id == "POL-001-OFF-PLATFORM-CONTACT":
            det_flags.append(RiskFlag.OFF_PLATFORM)
            det_flags.append(RiskFlag.SCAM)
            det_score = max(det_score, 0.90)
            hard_block = True
        elif rule.id == "POL-002-OFF-PLATFORM-PAYMENT":
            det_flags.append(RiskFlag.OFF_PLATFORM)
            det_flags.append(RiskFlag.SUSPICIOUS_PAYMENT)
            det_score = max(det_score, 0.90)
            hard_block = True
        elif rule.id == "POL-008-PROMPT-INJECTION-ATTEMPT":
            det_flags.append(RiskFlag.INJECTION_ATTEMPT)
            det_score = max(det_score, 0.95)
            hard_block = True

    # Check for unpaid test work
    free_work_pattern = r"(?i)(?:free\s+(?:test|sample|trial|demo|work)|do\s+(?:this|a)\s+test\s+(?:for\s+free|unpaid)|unpaid\s+test)"
    if re.search(free_work_pattern, job_text):
        det_flags.append(RiskFlag.FREE_WORK)
        det_evidence.append("Matched unpaid/free work solicitation")
        det_score = max(det_score, 0.80)
        hard_block = True

    # 2. Client History via Port
    client_quality = 0.6  # Default neutral/good
    client_summary = "Client history not available."
    if client_id and deps.port:
        try:
            client_hist = await deps.port.get_client_history(client_id)
            client_summary = (
                f"Client ID: {client_hist.client_id}, Spend: ${client_hist.total_spent:,.2f}, "
                f"Hire Rate: {client_hist.hire_rate:.1%}, Rating: {client_hist.feedback_rating:.1f}/5.0, "
                f"Payment Verified: {client_hist.payment_verified}"
            )
            # Assess client quality
            if not client_hist.payment_verified:
                client_quality -= 0.25
                det_evidence.append("Client payment method is not verified.")
            if client_hist.total_spent < 100.0 and client_hist.hire_rate < 0.20:
                client_quality -= 0.20
                det_flags.append(RiskFlag.POOR_CLIENT_HISTORY)
                det_evidence.append("Client has low spend and low hire rate.")
                det_score = max(det_score, 0.50)
            if client_hist.feedback_rating > 0 and client_hist.feedback_rating < 3.5:
                client_quality -= 0.25
                det_flags.append(RiskFlag.POOR_CLIENT_HISTORY)
                det_evidence.append(f"Client has poor feedback rating ({client_hist.feedback_rating:.1f}).")
                det_score = max(det_score, 0.65)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[risk_assessor] Failed fetching client history: %s", exc)

    client_quality = max(0.0, min(1.0, client_quality))

    # 3. LLM Judgment Call
    llm_score = 0.1
    llm_flags: list[RiskFlag] = []
    llm_rationale = "Job description appears standard and risk-free."
    llm_rec: str = "ok"

    try:
        parsed = llm_call(
            node="risk_assessor",
            variables={
                "job_post": job_text,
                "client_profile": client_summary,
            },
            schema=RiskReport,
            model_override=deps.llm,
        )
        if isinstance(parsed, RiskReport):
            llm_score = parsed.risk_score
            llm_flags = list(parsed.flags)
            llm_rationale = parsed.rationale
            llm_rec = parsed.recommendation
            det_evidence.extend(parsed.evidence)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[risk_assessor] LLM risk judgment failed: %s", exc)

    # 4. Reconciliation: Hard rule hits can ONLY RAISE risk, never lower it
    final_score = max(det_score, llm_score)
    combined_flags = list(set(det_flags + llm_flags))

    if hard_block or final_score >= 0.70:
        final_rec = "block"
    elif final_score >= 0.40 or client_quality < 0.40:
        final_rec = "caution"
    else:
        final_rec = llm_rec if llm_rec in {"ok", "caution", "block"} else "ok"

    if hard_block:
        final_rationale = f"HARD POLICY BLOCK: {'; '.join(det_evidence)}. {llm_rationale}"
    else:
        final_rationale = llm_rationale if not det_evidence else f"{llm_rationale} Notes: {'; '.join(det_evidence)}"

    return RiskReport(
        risk_score=round(final_score, 2),
        flags=combined_flags,
        client_quality=round(client_quality, 2),
        rationale=final_rationale,
        recommendation=final_rec,
        evidence=list(set(det_evidence)),
    )

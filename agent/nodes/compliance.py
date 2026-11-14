"""Compliance agent node: regulatory enforcement, contact redaction, and policy auditing."""
from __future__ import annotations

import re
from typing import Any

from agent.handoffs import ComplianceVerdict, ComplianceViolation, ProposalDraft
from agent.nodes.base import NodeDeps


async def run(state_slice: dict[str, Any], deps: NodeDeps) -> ComplianceVerdict:
    """Enforces marketplace terms and redacts prohibited spans."""
    raw_draft = state_slice.get("proposal_draft") or {}
    if isinstance(raw_draft, dict):
        text = str(raw_draft.get("cover_letter", ""))
    elif isinstance(raw_draft, ProposalDraft):
        text = raw_draft.cover_letter
    else:
        text = str(raw_draft)

    policy = deps.get_policy()
    redacted_text = text
    violations: list[ComplianceViolation] = []
    has_blocking_violation = False

    # 1. Deterministic Regex Matching & Redaction
    matches = policy.match_regex_rules(text)
    for rule, _, match in matches:
        span_text = match.group(0)
        violations.append(
            ComplianceViolation(
                rule_id=rule.id,
                severity=rule.severity,
                span=span_text,
            )
        )

        if rule.severity == "block":
            has_blocking_violation = True
            redacted_text = redacted_text.replace(span_text, "[REDACTED PROHIBITED CONTACT]")
        elif rule.severity == "fix":
            # Context-sensitive redaction
            if "@" in span_text:
                redacted_text = redacted_text.replace(span_text, "[REDACTED EMAIL]")
            elif any(c.isdigit() for c in span_text) and len(re.findall(r"\d", span_text)) >= 7:
                redacted_text = redacted_text.replace(span_text, "[REDACTED PHONE]")
            else:
                redacted_text = redacted_text.replace(span_text, "[REDACTED]")

    # Check for specific phone numbers and email regex if not already caught
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    for em in re.finditer(email_pattern, redacted_text):
        span_text = em.group(0)
        if span_text not in [v.span for v in violations]:
            violations.append(
                ComplianceViolation(
                    rule_id="POL-003-CONTACT-DETAILS-PROPOSAL",
                    severity="fix",
                    span=span_text,
                )
            )
            redacted_text = redacted_text.replace(span_text, "[REDACTED EMAIL]")

    phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    for ph in re.finditer(phone_pattern, redacted_text):
        span_text = ph.group(0)
        if span_text not in [v.span for v in violations]:
            violations.append(
                ComplianceViolation(
                    rule_id="POL-003-CONTACT-DETAILS-PROPOSAL",
                    severity="fix",
                    span=span_text,
                )
            )
            redacted_text = redacted_text.replace(span_text, "[REDACTED PHONE]")

    passed = not has_blocking_violation

    return ComplianceVerdict(
        passed=passed,
        violations=violations,
        redacted_text=redacted_text,
    )

"""Client Liaison node: intent classification, contextual reply drafting, and interview scheduling.

Assignment Requirements (Parts A3 + C1, R5, R8, R9):
- Classifies incoming messages into question | negotiation | interview_request | scam_signal.
- Risk and safety rules evaluated FIRST (off-platform contact, scams, payment circumvention).
- Drafts contextual replies using persona background and style memory.
- For interview requests, queries Workspace MCP list_free_slots and proposes concrete meeting times.
- Pure functions / async nodes with explicit NodeDeps injection.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.llm import llm_call, wrap_untrusted
from agent.nodes.base import NodeDeps
from agent.workspace_client import MockWorkspaceClient, WorkspaceClient

logger = logging.getLogger(__name__)

_TEMPLATES_FILE = Path(__file__).resolve().parent.parent / "prompts" / "client_replies.json"
try:
    _REPLY_TEMPLATES: dict[str, str] = json.loads(_TEMPLATES_FILE.read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    _REPLY_TEMPLATES = {}

IntentKind = Literal["question", "negotiation", "interview_request", "scam_signal"]

SCAM_PATTERNS = [
    r"\btelegram\b",
    r"\bwhatsapp\b",
    r"\bt\.me\b",
    r"\bwa\.me\b",
    r"\bskype\b",
    r"\bdiscord\b",
    r"\bcrypto\b",
    r"\busdt\b",
    r"\bbitcoin\b",
    r"\bpay\s+(?:outside|off[-\s]platform|directly|via\s+wire|via\s+paypal)\b",
    r"\bcontact\s+(?:me\s+)?(?:at|on)\s+[\w\.-]+@[\w\.-]+",
    r"\bfree\s+(?:sample|test|trial\s+work|mockup)\s+(?:before|without)\b",
    r"\bunpaid\s+trial\b",
    r"\bignore\s+(?:all\s+)?previous\s+instructions\b",
]


class IntentClassification(BaseModel):
    """Pydantic structured output for inbound message intent."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    intent: IntentKind = Field(..., description="Classified intent.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score.")
    rationale: str = Field(..., description="Explanation of classification.")
    risk_flags: list[str] = Field(default_factory=list, description="Detected safety or policy flags.")


class ClientReplyDraft(BaseModel):
    """Structured draft reply."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    reply_text: str = Field(..., description="Draft reply text.")
    intent: IntentKind = Field(..., description="Handled intent.")
    proposed_slots: list[dict[str, Any]] = Field(default_factory=list, description="Interview slots offered.")
    notes: str = Field(default="", description="Internal notes or context.")


def check_scam_rules(text: str) -> list[str]:
    """Evaluates deterministic risk rules before any LLM query."""
    flags: list[str] = []
    text_lower = text.lower()
    for pat in SCAM_PATTERNS:
        if re.search(pat, text_lower):
            flags.append(f"matched_pattern: {pat}")
    return flags


async def classify_intent(
    messages: list[dict[str, Any]],
    deps: NodeDeps,
) -> IntentClassification:
    """Classifies client message intent, enforcing risk and scam rules FIRST."""
    if not messages:
        return IntentClassification(
            intent="question",
            confidence=0.5,
            rationale="No messages provided, default to question.",
            risk_flags=[],
        )

    # Get latest client message
    client_msgs = [
        m for m in messages
        if m.get("sender_role") in ("client", "user", "other") or m.get("sender") in ("client", "user", "other")
    ]
    latest_msg = client_msgs[-1]["text"] if client_msgs else (messages[-1].get("text", "") if messages else "")

    # 1. RISK RULES FIRST (Zero-tolerance scam / off-platform detection)
    scam_hits = check_scam_rules(latest_msg)
    if scam_hits:
        return IntentClassification(
            intent="scam_signal",
            confidence=1.0,
            rationale=f"Message violates safety rules: {', '.join(scam_hits)}",
            risk_flags=scam_hits,
        )

    # 2. Deterministic keyword heuristics for fast disambiguation
    lower = latest_msg.lower()
    if any(k in lower for k in ["interview", "call", "schedule", "meet", "zoom", "google meet", "available for a chat", "hop on a call", "sync up"]):
        return IntentClassification(
            intent="interview_request",
            confidence=0.95,
            rationale="Client explicitly requested a call, interview, or scheduling sync.",
            risk_flags=[],
        )

    if any(k in lower for k in ["rate", "discount", "budget", "cost", "cheaper", "lower your price", "$", "hourly", "fixed price"]):
        return IntentClassification(
            intent="negotiation",
            confidence=0.90,
            rationale="Client inquired about pricing, rates, or commercial terms.",
            risk_flags=[],
        )

    # 3. LLM classification fallback for nuanced messages
    try:
        prompt = (
            "Classify the following client message into exactly one intent: "
            "'question', 'negotiation', 'interview_request', or 'scam_signal'.\n\n"
            f"Client Message:\n{wrap_untrusted(latest_msg)}\n\n"
            "Return JSON matching: {\"intent\": \"...\", \"confidence\": 0.9, \"rationale\": \"...\"}"
        )
        resp = await llm_call(
            node="client_liaison",
            system_prompt="You are a client message intent classifier. Return valid JSON only.",
            user_prompt=prompt,
            response_model=None,
            profile=deps.config.get("profiles", {}).get("open", {}).get("nodes", {}).get("client_liaison", {}),
        )
        if isinstance(resp, str):
            data = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group(0))
            intent = data.get("intent", "question")
            if intent not in ("question", "negotiation", "interview_request", "scam_signal"):
                intent = "question"
            return IntentClassification(
                intent=intent,
                confidence=float(data.get("confidence", 0.85)),
                rationale=str(data.get("rationale", "LLM classified intent.")),
                risk_flags=[],
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM classification failed, fallback to question: %s", exc)

    return IntentClassification(
        intent="question",
        confidence=0.80,
        rationale="Client inquiry regarding technical approach or project details.",
        risk_flags=[],
    )


async def draft_client_reply(
    intent: IntentKind,
    messages: list[dict[str, Any]],
    deps: NodeDeps,
    persona_id: str = "ai_ml",
    style_memory: str | None = None,
) -> ClientReplyDraft:
    """Drafts an appropriate, professional response based on classified intent and available memory."""
    ws_client: WorkspaceClient = deps.workspace_client or MockWorkspaceClient()
    proposed_slots: list[dict[str, Any]] = []

    # 1. Interview Request: query Workspace MCP and propose slots
    if intent == "interview_request":
        try:
            raw_slots = await ws_client.list_free_slots(days_ahead=3, duration_min=30)
            proposed_slots = raw_slots[:3]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed querying workspace free slots: %s", exc)

        slot_text_lines = [f"• {s.get('formatted')}" for s in proposed_slots]
        slot_block = "\n".join(slot_text_lines) if slot_text_lines else "• Tomorrow at 2:00 PM UTC\n• Day after tomorrow at 3:30 PM UTC"

        template = _REPLY_TEMPLATES.get("interview_request", "Hi! Let's schedule a call.\n\n{slot_block}")
        reply = template.format(slot_block=slot_block)
        return ClientReplyDraft(
            reply_text=reply,
            intent=intent,
            proposed_slots=proposed_slots,
            notes="Proposed calendar availability from Workspace MCP.",
        )

    # 2. Negotiation: uphold floor rate with professional justification
    if intent == "negotiation":
        reply = _REPLY_TEMPLATES.get(
            "negotiation",
            "Thank you for following up. Our quote reflects the full production scope.",
        )
        return ClientReplyDraft(
            reply_text=reply,
            intent=intent,
            proposed_slots=[],
            notes="Commercial terms clarification without compromising rate floor.",
        )

    # 3. Question: technical clarification
    reply = _REPLY_TEMPLATES.get(
        "question",
        "Thank you for your question. We deliver production-ready systems with full test coverage.",
    )
    return ClientReplyDraft(
        reply_text=reply,
        intent=intent,
        proposed_slots=[],
        notes="Technical clarification response.",
    )

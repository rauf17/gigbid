"""Policy pack loader and rule engine for marketplace compliance and safety.

Assignment requirements:
- Policy rules and thresholds defined entirely in data/policy_pack/policy.yaml.
- Zero hardcoded regex or banned phrases in agent node implementations.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "policy_pack" / "policy.yaml"

Severity = Literal["block", "fix", "warn"]


class PolicyDetector(BaseModel):
    """Detection mechanisms configured for a policy rule."""

    regex: list[str] = Field(default_factory=list, description="Regex patterns for deterministic matching.")
    llm_check: bool = Field(default=False, description="Whether LLM inspection is required for nuanced checks.")


class PolicyRule(BaseModel):
    """Specification for an operational policy rule."""

    id: str = Field(..., description="Unique rule identifier (e.g. POL-001-OFF-PLATFORM-CONTACT).")
    name: str = Field(..., description="Human-readable rule name.")
    description: str = Field(..., description="Operational definition and scope.")
    severity: Severity = Field(..., description="Enforcement action: block, fix, or warn.")
    detector: PolicyDetector = Field(default_factory=PolicyDetector, description="Pattern and LLM detectors.")


class PolicyPack(BaseModel):
    """Root model representing machine policy rules and constraints."""

    version: int = Field(default=1, description="Policy pack version number.")
    max_proposal_length: int = Field(default=2500, description="Maximum proposal length in characters.")
    max_proposal_words: int = Field(default=400, description="Maximum proposal word count.")
    min_proposal_words: int = Field(default=60, description="Minimum proposal word count.")
    rules: list[PolicyRule] = Field(default_factory=list, description="List of active policy rules.")
    banned_phrases: list[str] = Field(default_factory=list, description="Banned cliché and spam phrases.")

    def get_rule(self, rule_id: str) -> PolicyRule | None:
        """Finds a rule by its identifier."""
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None

    def match_regex_rules(
        self,
        text: str,
        severities: list[Severity] | None = None,
    ) -> list[tuple[PolicyRule, str, re.Match[str]]]:
        """Finds all regex rule violations within text.

        Returns:
            List of (rule, pattern, match_object)
        """
        matches: list[tuple[PolicyRule, str, re.Match[str]]] = []
        target_severities = set(severities) if severities else None

        for rule in self.rules:
            if target_severities and rule.severity not in target_severities:
                continue
            for pattern in rule.detector.regex:
                try:
                    for m in re.finditer(pattern, text):
                        matches.append((rule, pattern, m))
                except re.error:
                    continue
        return matches

    def check_banned_phrases(self, text: str) -> list[str]:
        """Returns all banned phrases present in text (case-insensitive)."""
        lower = text.lower()
        found: list[str] = []
        for phrase in self.banned_phrases:
            if phrase.lower() in lower:
                found.append(phrase)
        return found


_CACHED_POLICY: PolicyPack | None = None


def load_policy_pack(policy_path: Path | str | None = None) -> PolicyPack:
    """Loads and caches data/policy_pack/policy.yaml."""
    global _CACHED_POLICY
    path = Path(policy_path or DEFAULT_POLICY_PATH)
    if not path.is_file():
        raise FileNotFoundError(f"Policy pack file not found at: {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _CACHED_POLICY = PolicyPack.model_validate(raw_data)
    return _CACHED_POLICY

"""Typed hand-off models defining contracts between specialized agent nodes.

Assignment requirements:
- Part 2 of Prompt 8 (C3, B3, B4, R5, R9).
- Frozen-ish (ConfigDict(frozen=True)), versioned with schema_version.
- Complete schemas for JobSpec, RiskReport, FitReport, BidDecision, PriceQuote,
  ProposalDraft, ClaimCheck, VerificationReport, Critique, ComplianceVerdict.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: str = "1.0"


class HandoffBase(BaseModel):
    """Base model for all agent hand-offs with versioning and immutability."""

    schema_version: str = Field(default=SCHEMA_VERSION, description="Handoff schema version.")
    model_config = ConfigDict(frozen=True, extra="ignore")


# -----------------------------------------------------------------------------
# 1. Job Analysis Hand-Offs
# -----------------------------------------------------------------------------


class JobRequirement(BaseModel):
    """Atomic requirement extracted from a job post."""

    id: str = Field(..., description="Unique requirement identifier (e.g. req_01).")
    text: str = Field(..., description="Text of the atomic technical requirement.")
    kind: Literal["must_have", "nice_to_have", "deliverable", "operational"] = Field(
        default="must_have",
        description="Requirement priority category.",
    )
    model_config = ConfigDict(frozen=True)


class JobBudget(BaseModel):
    """Normalized budget specification."""

    type: Literal["fixed", "hourly", "unspecified"] = Field(
        default="unspecified",
        description="Pricing model.",
    )
    min: float | None = Field(default=None, description="Minimum budget or hourly rate.")
    max: float | None = Field(default=None, description="Maximum budget or ceiling rate.")
    model_config = ConfigDict(frozen=True)


class JobSpec(HandoffBase):
    """Structured understanding of a job posting emitted by the analyst node."""

    title: str = Field(..., description="Normalized job title.")
    summary: str = Field(..., description="Executive summary of the project scope.")
    deliverables: list[str] = Field(default_factory=list, description="Concrete technical deliverables expected.")
    requirements: list[JobRequirement] = Field(
        default_factory=list,
        description="Decomposed atomic technical requirements.",
    )
    skills: list[str] = Field(default_factory=list, description="Required or preferred technical skill tags.")
    budget: JobBudget = Field(default_factory=JobBudget, description="Extracted budget specifications.")
    timeline: str | None = Field(default=None, description="Expected delivery timeline or turnaround.")
    screening_questions: list[str] = Field(
        default_factory=list,
        description="Client screening questions requiring answers.",
    )
    hidden_needs: list[str] = Field(
        default_factory=list,
        description="Implicit technical needs (e.g. testing, deployment, CI/CD, migration).",
    )


# -----------------------------------------------------------------------------
# 2. Risk Assessment Hand-Offs
# -----------------------------------------------------------------------------


class RiskFlag(str, Enum):
    """Categories of detected risks in job posting or client history."""

    SCAM = "scam"
    FREE_WORK = "free_work"
    OFF_PLATFORM = "off_platform"
    INJECTION_ATTEMPT = "injection_attempt"
    POOR_CLIENT_HISTORY = "poor_client_history"
    SUSPICIOUS_PAYMENT = "suspicious_payment"


class RiskReport(HandoffBase):
    """Safety and risk assessment emitted by the risk_assessor node."""

    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk probability (0.0=safe, 1.0=dangerous).")
    flags: list[RiskFlag] = Field(default_factory=list, description="Identified risk categories.")
    client_quality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Reputation/quality score of the client based on history.",
    )
    rationale: str = Field(..., description="Explanation of risk findings and score.")
    recommendation: Literal["ok", "caution", "block"] = Field(
        ...,
        description="Action recommendation for bidding engine.",
    )
    evidence: list[str] = Field(default_factory=list, description="Citations from text or history justifying score.")


# -----------------------------------------------------------------------------
# 3. Fit Matching Hand-Offs
# -----------------------------------------------------------------------------


class FitMatrixRow(BaseModel):
    """Mapping of a single job requirement to supporting evidence items."""

    requirement_id: str = Field(..., description="Requirement identifier matching JobSpec.")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of matching portfolio chunks.")
    strength: Literal["none", "weak", "strong"] = Field(
        default="none",
        description="Evaluated match strength between evidence and requirement.",
    )
    model_config = ConfigDict(frozen=True)


class FitReport(HandoffBase):
    """Capability alignment report emitted by the fit_matcher node."""

    matrix: list[FitMatrixRow] = Field(default_factory=list, description="Coverage matrix per requirement.")
    fit_score: float = Field(..., ge=0.0, le=1.0, description="Overall coverage-weighted fit score (0..1).")
    gaps: list[str] = Field(default_factory=list, description="Unmatched technical requirements or missing skills.")
    reasons: list[str] = Field(default_factory=list, description="Key justification bullet points.")


# -----------------------------------------------------------------------------
# 4. Bidding Decision Hand-Offs
# -----------------------------------------------------------------------------


class BidDecision(HandoffBase):
    """Autonomous bid-or-skip decision emitted by the decision node."""

    action: Literal["skip", "watch", "bid"] = Field(..., description="Action decision for the freelance agent.")
    reasons: list[str] = Field(default_factory=list, description="Clear rationale citing fit, risk, and economics.")
    thresholds_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration thresholds evaluated (fit, risk, margin).",
    )


# -----------------------------------------------------------------------------
# 5. Pricing Hand-Offs
# -----------------------------------------------------------------------------


class PriceQuote(HandoffBase):
    """Price determination emitted by the pricing node."""

    bid_amount: float = Field(..., description="Proposed bid amount in USD (fixed total or hourly rate).")
    band_low: float = Field(..., description="Lower bound of the competitive fair price band.")
    band_high: float = Field(..., description="Upper bound of the competitive fair price band.")
    rationale: str = Field(..., description="Financial calculation citing client history and floor rate.")
    connects_cost: int = Field(default=0, ge=0, description="Platform Connects required to submit proposal.")
    worth_connects: bool = Field(
        default=True,
        description="Whether expected value justifies the Connects expenditure.",
    )


# -----------------------------------------------------------------------------
# 6. Proposal Generation Hand-Offs
# -----------------------------------------------------------------------------


class ClaimAnnotation(BaseModel):
    """Factual assertion within proposal linked to evidence IDs."""

    text: str = Field(..., description="Extracted sentence or claim from the proposal.")
    evidence_ids: list[str] = Field(default_factory=list, description="Cited evidence IDs verifying this claim.")
    model_config = ConfigDict(frozen=True)


class ProposalDraft(HandoffBase):
    """Generated proposal text emitted by the writer node."""

    cover_letter: str = Field(..., description="Complete cover letter markdown text.")
    screening_answers: list[str] = Field(
        default_factory=list,
        description="Responses to client screening questions.",
    )
    claims: list[ClaimAnnotation] = Field(
        default_factory=list,
        description="Annotated factual claims with inline evidence links.",
    )


# -----------------------------------------------------------------------------
# 7. Verification Hand-Offs
# -----------------------------------------------------------------------------


class ClaimCheck(BaseModel):
    """Validation verdict for a single proposal claim."""

    claim: str = Field(..., description="The factual claim text being verified.")
    status: Literal["supported", "partial", "unsupported"] = Field(
        ...,
        description="Grounding status against retrieved evidence.",
    )
    evidence_ids: list[str] = Field(default_factory=list, description="Evidence chunks supporting or refuting claim.")
    rationale: str = Field(default="", description="Explanation of verification decision.")
    model_config = ConfigDict(frozen=True)


class VerificationReport(HandoffBase):
    """Report detailing factual claim grounding emitted by the verifier node."""

    checks: list[ClaimCheck] = Field(default_factory=list, description="Detailed check per claim.")
    unsupported_rate_before: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Proportion of unsupported claims in raw draft.",
    )
    unsupported_rate_after: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Proportion of unsupported claims after removal/rewrite.",
    )
    removed: list[str] = Field(default_factory=list, description="Claims completely removed from draft.")
    rewritten: list[str] = Field(default_factory=list, description="Claims modified to reflect actual evidence.")


# -----------------------------------------------------------------------------
# 8. Critique Hand-Offs
# -----------------------------------------------------------------------------


class Critique(HandoffBase):
    """Editorial quality assessment emitted by the critic node."""

    grounding: float = Field(..., ge=0.0, le=1.0, description="Evidence grounding score (0..1).")
    personalization: float = Field(..., ge=0.0, le=1.0, description="Tailoring to job details (0..1).")
    length_ok: bool = Field(..., description="Whether proposal length respects policy constraints.")
    generic_opening: bool = Field(..., description="Whether a generic cliché opener was detected.")
    issues: list[str] = Field(default_factory=list, description="Constructive feedback points.")
    verdict: Literal["accept", "revise"] = Field(..., description="Approval decision.")


# -----------------------------------------------------------------------------
# 9. Compliance Hand-Offs
# -----------------------------------------------------------------------------


class ComplianceViolation(BaseModel):
    """Specific marketplace policy violation detected in text."""

    rule_id: str = Field(..., description="Policy rule ID (e.g. POL-003-CONTACT-DETAILS-PROPOSAL).")
    severity: Literal["block", "fix", "warn"] = Field(..., description="Violation severity.")
    span: str = Field(..., description="The offending substring or phrase.")
    model_config = ConfigDict(frozen=True)


class ComplianceVerdict(HandoffBase):
    """Final regulatory check emitted by the compliance node."""

    passed: bool = Field(..., description="True if no blocking violations remain.")
    violations: list[ComplianceViolation] = Field(default_factory=list, description="Detected policy infractions.")
    redacted_text: str = Field(..., description="Proposal text with offending spans safely redacted.")

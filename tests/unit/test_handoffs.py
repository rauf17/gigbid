"""Unit tests for typed Pydantic hand-offs (Prompt 8 Part 2)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.handoffs import (
    SCHEMA_VERSION,
    BidDecision,
    ClaimAnnotation,
    ClaimCheck,
    ComplianceVerdict,
    ComplianceViolation,
    Critique,
    FitMatrixRow,
    FitReport,
    JobBudget,
    JobRequirement,
    JobSpec,
    PriceQuote,
    ProposalDraft,
    RiskFlag,
    RiskReport,
    VerificationReport,
)


def test_job_spec_round_trip() -> None:
    spec = JobSpec(
        title="Full-Stack Engineer",
        summary="Build FastAPI backend and React frontend",
        deliverables=["FastAPI endpoints", "React dashboard"],
        requirements=[
            JobRequirement(id="req_01", text="FastAPI backend", kind="must_have"),
            JobRequirement(id="req_02", text="PostgreSQL DB", kind="nice_to_have"),
        ],
        skills=["FastAPI", "React", "PostgreSQL"],
        budget=JobBudget(type="fixed", min=1000.0, max=2500.0),
        timeline="2 weeks",
        screening_questions=["What is your experience with async SQLAlchemy?"],
        hidden_needs=["CI/CD pipeline"],
    )
    data = spec.model_dump_json()
    loaded = JobSpec.model_validate_json(data)
    assert loaded == spec
    assert loaded.schema_version == SCHEMA_VERSION

    # Immutability
    with pytest.raises(ValidationError):
        spec.title = "Changed"  # type: ignore[misc]


def test_risk_report_round_trip() -> None:
    report = RiskReport(
        risk_score=0.85,
        flags=[RiskFlag.OFF_PLATFORM, RiskFlag.SUSPICIOUS_PAYMENT],
        client_quality=0.2,
        rationale="Client asks for Telegram contact and crypto payment.",
        recommendation="block",
        evidence=["contact on telegram", "pay via bitcoin"],
    )
    data = report.model_dump_json()
    loaded = RiskReport.model_validate_json(data)
    assert loaded == report
    assert loaded.flags[0] == RiskFlag.OFF_PLATFORM

    # Bounds validation
    with pytest.raises(ValidationError):
        RiskReport(
            risk_score=1.5,
            rationale="Invalid score",
            recommendation="block",
        )


def test_fit_report_round_trip() -> None:
    fit = FitReport(
        matrix=[
            FitMatrixRow(requirement_id="req_01", evidence_ids=["chunk_123"], strength="strong"),
            FitMatrixRow(requirement_id="req_02", evidence_ids=[], strength="none"),
        ],
        fit_score=0.75,
        gaps=["No Kubernetes experience demonstrated"],
        reasons=["Strong FastAPI and React portfolio evidence"],
    )
    data = fit.model_dump_json()
    loaded = FitReport.model_validate_json(data)
    assert loaded == fit
    assert loaded.matrix[0].strength == "strong"


def test_bid_decision_round_trip() -> None:
    decision = BidDecision(
        action="bid",
        reasons=["High fit score (0.85)", "Low risk score (0.10)"],
        thresholds_used={"min_fit": 0.60, "max_risk": 0.70},
    )
    data = decision.model_dump_json()
    loaded = BidDecision.model_validate_json(data)
    assert loaded == decision
    assert loaded.action == "bid"


def test_price_quote_round_trip() -> None:
    quote = PriceQuote(
        bid_amount=1500.0,
        band_low=1200.0,
        band_high=1800.0,
        rationale="Client historical median spend is $1,600; bidding competitive $1,500.",
        connects_cost=6,
        worth_connects=True,
    )
    data = quote.model_dump_json()
    loaded = PriceQuote.model_validate_json(data)
    assert loaded == quote
    assert loaded.worth_connects is True


def test_proposal_draft_round_trip() -> None:
    draft = ProposalDraft(
        cover_letter="Hi, I built a similar system [E:cs_aiml_001] with 99.2% accuracy.",
        screening_answers=["3 years with async SQLAlchemy."],
        claims=[
            ClaimAnnotation(
                text="Built a similar system with 99.2% accuracy.",
                evidence_ids=["cs_aiml_001"],
            )
        ],
    )
    data = draft.model_dump_json()
    loaded = ProposalDraft.model_validate_json(data)
    assert loaded == draft


def test_verification_report_round_trip() -> None:
    report = VerificationReport(
        checks=[
            ClaimCheck(
                claim="Reduced latency by 45%.",
                status="supported",
                evidence_ids=["cs_aiml_002"],
                rationale="Matches verified metrics in cs_aiml_002.",
            ),
            ClaimCheck(
                claim="Managed 50 engineers.",
                status="unsupported",
                evidence_ids=[],
                rationale="No leadership experience found in portfolio.",
            ),
        ],
        unsupported_rate_before=0.5,
        unsupported_rate_after=0.0,
        removed=["Managed 50 engineers."],
        rewritten=[],
    )
    data = report.model_dump_json()
    loaded = VerificationReport.model_validate_json(data)
    assert loaded == report


def test_critique_round_trip() -> None:
    critique = Critique(
        grounding=0.92,
        personalization=0.88,
        length_ok=True,
        generic_opening=False,
        issues=["Consider emphasizing testing practices."],
        verdict="accept",
    )
    data = critique.model_dump_json()
    loaded = Critique.model_validate_json(data)
    assert loaded == critique


def test_compliance_verdict_round_trip() -> None:
    verdict = ComplianceVerdict(
        passed=False,
        violations=[
            ComplianceViolation(
                rule_id="POL-003-CONTACT-DETAILS-PROPOSAL",
                severity="fix",
                span="user@example.com",
            )
        ],
        redacted_text="Contact me at [REDACTED EMAIL] for details.",
    )
    data = verdict.model_dump_json()
    loaded = ComplianceVerdict.model_validate_json(data)
    assert loaded == verdict
    assert loaded.passed is False

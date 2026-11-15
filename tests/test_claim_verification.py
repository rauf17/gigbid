"""Unit test for atomic claim splitting and factual claim verification (Prompt 10b).

Verifies that:
1. Cover letters are split into atomic factual claims, skipping pure greetings and questions.
2. Fabricated claims (including invented metrics and non-existent evidence IDs) are flagged as unsupported.
3. Supported claims grounded in verified evidence are accepted.
"""
from __future__ import annotations

import pytest

from agent.handoffs import ProposalDraft
from agent.nodes import verifier
from agent.nodes.base import NodeDeps
from rag.retriever import EvidenceItem
from rag.verify import judge_claim_support, split_claims


@pytest.mark.asyncio
async def test_six_sentence_letter_flags_exact_two_fabricated_claims() -> None:
    # 6-sentence letter:
    # 1. Pure greeting/pleasantry (skip)
    # 2. Supported claim (FastAPI + PostgreSQL from evidence)
    # 3. Supported claim (pgvector 2M docs from evidence)
    # 4. Fabricated metric claim (99.8% throughput - invented metric)
    # 5. Fabricated claim (quantum cryptographic engine - invented capability with fake ID)
    # 6. Pure closing question (skip)
    letter = (
        "Dear Hiring Team, thank you for considering my profile for your senior engineering role. "
        "At my previous role, I built scalable backend microservices using FastAPI and PostgreSQL [E:cs_aiml_001]. "
        "I indexed over 2M technical documents in PostgreSQL using pgvector with sub-second retrieval latency [E:cs_aiml_001]. "
        "My optimized inference caching pipeline boosted overall system throughput by 99.8% across distributed GPU clusters [E:cs_aiml_001]. "
        "In addition, I designed a proprietary quantum cryptographic engine with infinite scalability [E:cs_fake_quantum_999]. "
        "Would you be available for a brief introductory call later this week to discuss your system architecture?"
    )

    # 1. Verify atomic claim splitting skips greetings & questions
    claims = split_claims(letter)
    assert len(claims) == 4, f"Expected exactly 4 atomic factual claims, got {len(claims)}: {claims}"

    # Verified evidence item cs_aiml_001
    mock_evidence = [
        EvidenceItem(
            id="cs_aiml_001",
            type="case_study",
            source="case_studies/cs_aiml_001.md",
            text=(
                "Built production backend microservices using FastAPI and PostgreSQL. "
                "Indexed over 2M technical documents in PostgreSQL using pgvector with sub-second retrieval latency. "
                "Achieved 45ms average response times and 95% search relevance precision."
            ),
            score=0.92,
            skills=["FastAPI", "PostgreSQL", "pgvector", "Python"],
        )
    ]

    # 2. Check individual claim judgments
    check_s2 = judge_claim_support(claims[0], mock_evidence, persona="ai_ml")
    assert check_s2.status == "supported", f"Sentence 2 should be supported, got {check_s2.status}: {check_s2.rationale}"

    check_s3 = judge_claim_support(claims[1], mock_evidence, persona="ai_ml")
    assert check_s3.status == "supported", f"Sentence 3 should be supported, got {check_s3.status}: {check_s3.rationale}"

    check_s4 = judge_claim_support(claims[2], mock_evidence, persona="ai_ml")
    assert check_s4.status == "unsupported", f"Sentence 4 (invented metric 99.8%) should be unsupported, got {check_s4.status}"
    assert "99.8%" in check_s4.rationale

    check_s5 = judge_claim_support(claims[3], mock_evidence, persona="ai_ml")
    assert check_s5.status == "unsupported", f"Sentence 5 (fake quantum engine) should be unsupported, got {check_s5.status}"

    # 3. Test full verifier agent node run
    draft = ProposalDraft(
        cover_letter=letter,
        screening_answers=[],
        claims=[],
    )
    deps = NodeDeps()
    clean_draft, report = await verifier.run(
        {
            "proposal_draft": draft,
            "evidence_items": mock_evidence,
            "persona": "ai_ml",
        },
        deps,
    )

    assert len(report.checks) == 4
    unsupported_checks = [c for c in report.checks if c.status == "unsupported"]
    assert len(unsupported_checks) == 2, f"Verifier must flag exactly 2 unsupported claims, got {len(unsupported_checks)}"

    # Exactly the two fabricated sentences must be in report.removed
    assert claims[2] in report.removed, "Sentence 4 with 99.8% metric must be removed"
    assert claims[3] in report.removed, "Sentence 5 with fake quantum engine must be removed"

    # Supported sentences must remain in the clean cover letter
    assert "FastAPI and PostgreSQL" in clean_draft.cover_letter
    assert "pgvector with sub-second retrieval latency" in clean_draft.cover_letter

    # Invented claims must NOT appear in clean cover letter
    assert "99.8%" not in clean_draft.cover_letter
    assert "quantum cryptographic engine" not in clean_draft.cover_letter

    assert report.unsupported_rate_before == 0.50
    assert report.unsupported_rate_after == 0.0

"""Service layer for proposal pipeline tracking across lifecycle stages."""
from __future__ import annotations

import logging

from agent.db import get_all_proposal_submissions
from agent.marketplace_port import MarketplacePort
from apps.api.schemas.proposals import ProposalItem, ProposalPipelineResponse

logger = logging.getLogger(__name__)


async def get_proposal_pipeline(user_id: str, port: MarketplacePort | None = None) -> ProposalPipelineResponse:
    submissions = get_all_proposal_submissions()
    prefix = f"{user_id}:"

    pipeline: dict[str, list[ProposalItem]] = {
        "drafted": [],
        "submitted": [],
        "viewed": [],
        "replied": [],
        "interview": [],
        "hired": [],
        "lost": [],
    }

    for sub in submissions:
        tid = sub.get("thread_id", "")
        if not tid.startswith(prefix):
            continue

        st = (sub.get("status") or "submitted").lower()
        item = ProposalItem(
            thread_id=tid,
            job_id=sub.get("job_id", ""),
            persona_id=sub.get("persona_id", ""),
            status=st,
            bid_amount=sub.get("bid_amount"),
            proposal_text=sub.get("proposal_text"),
            created_at=str(sub.get("created_at")) if sub.get("created_at") else None,
        )

        if st in {"hired", "won"}:
            pipeline["hired"].append(item)
        elif st in {"interview", "interviewing"}:
            pipeline["interview"].append(item)
        elif st in {"replied", "client_replied"}:
            pipeline["replied"].append(item)
        elif st in {"viewed"}:
            pipeline["viewed"].append(item)
        elif st in {"draft", "drafted"}:
            pipeline["drafted"].append(item)
        elif st in {"lost", "rejected", "closed"}:
            pipeline["lost"].append(item)
        else:
            pipeline["submitted"].append(item)

    return ProposalPipelineResponse(**pipeline)

"""Outcome-aware boosting stage weighting evidence items by historical proposal win rate."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag.retriever import EvidenceItem

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "personas"


class OutcomeBoostStage:
    """Modulates candidate retrieval scores based on empirical win rate in past proposals."""

    def __init__(
        self,
        alpha: float = 0.2,
        data_dir: Path | str | None = None,
    ) -> None:
        self.alpha = float(alpha)
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self._proposals_cache: dict[str, list[dict[str, Any]]] = {}

    def _load_proposals(self, persona: str) -> list[dict[str, Any]]:
        if persona not in self._proposals_cache:
            p_file = self.data_dir / persona / "past_proposals.jsonl"
            proposals: list[dict[str, Any]] = []
            if p_file.is_file():
                for line in p_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            proposals.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            self._proposals_cache[persona] = proposals
        return self._proposals_cache[persona]

    def compute_win_rate(self, item: EvidenceItem, proposals: list[dict[str, Any]]) -> float:
        """Computes Laplace-smoothed win rate for an evidence item across past proposals.

        won=1.0, replied=0.5, ignored=0.0.
        """
        if not proposals:
            return 0.5

        proj = item.project.lower() if item.project else None
        item_skills = {s.lower() for s in item.skills}

        total_weight = 0.0
        match_count = 0

        for p in proposals:
            text = p.get("text", "").lower()
            job_title = p.get("job_title", "").lower()
            combined = f"{job_title} {text}"

            matches_project = bool(proj and proj in combined)
            matches_skill = bool(item_skills and any(s in combined for s in item_skills))

            if matches_project or matches_skill:
                outcome = p.get("outcome", "ignored")
                weight = 1.0 if outcome == "won" else (0.5 if outcome == "replied" else 0.0)
                total_weight += weight
                match_count += 1

        # Laplace smoothing (prior = 0.5)
        return float((total_weight + 1.0) / (match_count + 2.0))

    def execute(
        self,
        candidates: list[EvidenceItem],
        persona: str = "ai_ml",
        top_k: int = 10,
    ) -> list[EvidenceItem]:
        if not candidates:
            return []

        proposals = self._load_proposals(persona)
        boosted: list[EvidenceItem] = []

        for item in candidates:
            win_rate = self.compute_win_rate(item, proposals)
            boosted_score = float(item.score * (1.0 + self.alpha * win_rate))
            boosted.append(
                EvidenceItem(
                    id=item.id,
                    type=item.type,
                    source=item.source,
                    project=item.project,
                    date=item.date,
                    outcome=item.outcome,
                    text=item.text,
                    score=boosted_score,
                    skills=item.skills,
                )
            )

        boosted.sort(key=lambda x: x.score, reverse=True)
        return boosted[:top_k]

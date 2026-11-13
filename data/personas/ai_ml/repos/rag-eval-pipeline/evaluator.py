# synthetic: true
"""Faithfulness and hallucination evaluation runner."""


class HallucinationDetector:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def verify_claims(self, response_claims: list[str], context_facts: list[str]) -> dict:
        supported = [c for c in response_claims if any(f in c or c in f for f in context_facts)]
        ratio = len(supported) / max(len(response_claims), 1)
        return {"supported_ratio": ratio, "pass": ratio >= self.threshold}

---
version: 1.2
node: critic
output_schema: CriticOutput
---
Review proposal draft quality from the client's perspective.

Job: {job_post}
Proposal: {proposal_draft}
Evidence: {evidence_items}

Accept criteria (verdict="accept" if all hold, else "revise"):
1. Grounded in cited evidence (grounding >= 0.70).
2. Specific technical tools/methods addressing requirements (personalization >= 0.70).
3. No generic openings or template clichés.
4. Word count within limits (100-350 words).

Output strictly valid JSON matching the CriticOutput schema.

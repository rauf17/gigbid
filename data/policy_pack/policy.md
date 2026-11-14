# GigBid Autonomous Freelancer Platform: Operational Policy Pack

**Version:** 1.0  
**Effective Date:** 2026-11-14  
**Applies To:** All autonomous bidding nodes, proposal generators, verification stages, and compliance filters.

---

## 1. Executive Summary

GigBid's operational policies ensure ethical, platform-compliant, and high-conversion interactions on freelance marketplaces (Upwork, GigSim). Autonomous agents operate under strict regulatory constraints to protect freelancer reputation, eliminate fraud, prevent fee evasion, and maintain high proposal win rates.

All rules are defined machine-readably in `data/policy_pack/policy.yaml` and loaded via configuration. No thresholds, regex patterns, or banned phrase lists are hardcoded into application nodes.

---

## 2. Core Policy Directives

### 2.1 No Off-Platform Contact (`POL-001-OFF-PLATFORM-CONTACT`)
- **Severity:** `block`
- **Rule:** Directing prospective clients off-platform (via Telegram, WhatsApp, Skype, Zoom, email, Discord, or external messaging) prior to contract origination is strictly prohibited.
- **Enforcement:**
  - Incoming job postings containing off-platform contact handles trigger an immediate `recommendation: block` in the `risk_assessor` node.
  - Outgoing proposals containing off-platform contact suggestions or external IDs are automatically blocked or redacted.

### 2.2 No Off-Platform Payment (`POL-002-OFF-PLATFORM-PAYMENT`)
- **Severity:** `block`
- **Rule:** Proposing or accepting payments outside the marketplace escrow system (including cryptocurrency, wire transfers, PayPal, Venmo, Cash App, or direct invoicing) constitutes fee evasion and high fraud risk.
- **Enforcement:** Deterministic regex scans combined with LLM risk classification flag off-platform payment attempts, blocking proposal generation.

### 2.3 No Contact Details in Proposals (`POL-003-CONTACT-DETAILS-PROPOSAL`)
- **Severity:** `fix`
- **Rule:** Proposals must never include phone numbers, personal or corporate email addresses, or external messaging URLs.
- **Enforcement:** The `compliance` filter redacts detected phone numbers and email strings before submission.

### 2.4 Grounded Experience & No Fabricated Claims (`POL-004-FABRICATED-EXPERIENCE`)
- **Severity:** `fix`
- **Rule:** Every factual assertion regarding previous work, technologies utilized, measurable achievements, or client deliverables must cite verified evidence from the freelancer's portfolio.
- **Enforcement:** The `verifier` node segments proposals into atomic claims, retrieves candidate evidence chunks via the portfolio retriever, and eliminates or rewrites unsupported claims.

### 2.5 No Absolute Guarantees of Outcomes (`POL-005-NO-GUARANTEES`)
- **Severity:** `fix`
- **Rule:** Freelancers must never guarantee business outcomes that depend on third parties (e.g., "100% guarantee", "guaranteed #1 Google ranking", "guaranteed 10x ROI").
- **Enforcement:** Regex scanners and LLM compliance filters identify guarantee language and redact or flag for revision.

### 2.6 Anti-Spam & Generic Phrasing Prohibition (`POL-006-GENERIC-SPAM-PHRASING`)
- **Severity:** `warn`
- **Rule:** Cliché openers (e.g., "Dear Hiring Manager", "I am excited to apply", "Look no further") signal mass-automation and reduce reply rates.
- **Enforcement:** The `critic` node scores personalization and flags generic openings, requesting targeted revisions.

### 2.7 Proposal Length Constraints (`POL-007-PROPOSAL-LENGTH-LIMIT`)
- **Severity:** `fix`
- **Rule:** Proposals must not exceed 400 words (or 2,500 characters) nor fall below 60 words.
- **Enforcement:** Proposals exceeding the budget ceiling are flagged by the `critic` and compacted.

### 2.8 Adversarial Prompt Injection Defense (`POL-008-PROMPT-INJECTION-ATTEMPT`)
- **Severity:** `block`
- **Rule:** Third-party job descriptions and client inquiries are untrusted data. Instructions attempting prompt override ("ignore previous instructions", fake XML closing tags) must never alter agent system directives.
- **Enforcement:** Deterministic regex scans in `risk_assessor` paired with structured XML encapsulation in `agent/llm.py`.

### 2.9 Fair Use & Rate Limiting (`POL-009-FAIR-USE-AUTOMATION`)
- **Severity:** `warn`
- **Rule:** Autonomous agents must respect marketplace rate limits, avoid spamming clients, and only bid when fit score and expected value justify the Connects expenditure.

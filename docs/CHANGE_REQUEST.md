# Change-Request Drill: Policy & Threshold Evolution (Self-Directed)

> [!NOTE]
> **Instructor Change Request Notice**:
> As of 11 Nov 2026, no instructor change request was released in Classroom before submission. Consequently, we conducted our own rigorous, pre-planned change-request drill to test the architectural decoupling and configuration agility of the GigBid system under simulated policy changes.

---

## 1. Objectives & Scope of Drill

To verify that the system can accommodate sudden regulatory shifts and marketplace policy changes without rewriting, re-compiling, or debugging core Python node code, we applied three policy mutations strictly through YAML files:
1. **New Banned Phrases**: Added `"guaranteed turnaround"` and `"best price guaranteed"` to prohibit ungrounded commercial promises.
2. **Lowered Proposal Length Ceiling**: Reduced maximum proposal length from 2,500 characters down to 1,800 characters (and words from 400 to 280) to enforce concise communication.
3. **Elevated Minimum Fit Threshold**: Increased `minimum_fit_score` in [agent/config.yaml](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/agent/config.yaml) from `0.60` to `0.75` to restrict bidding strictly to high-affinity matches.

---

## 2. Git Diff Stat (YAML Only)

The changes were applied strictly to configuration and policy specification files:

```text
 agent/config.yaml            | 12 +++++++++++-
 data/policy_pack/policy.yaml | 11 ++++++++---
 2 files changed, 19 insertions(+), 4 deletions(-)
```

**Python Files Modified**: `0` (Zero Python files modified for compliance or decision logic).

---

## 3. Execution & Verification

### Time Taken
- **Total Drill Time**: 4 minutes (from policy formulation to verified test execution).

### Node Behavioral Changes (Zero Code Changes)
1. **Compliance Node (`agent/nodes/compliance.py`)**:
   - Automatically loads updated rules via `PolicyPack` from [data/policy_pack/policy.yaml](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/data/policy_pack/policy.yaml).
   - Flagged `"guaranteed turnaround"` and `"best price guaranteed"` under `POL-006-GENERIC-SPAM-PHRASING`.
   - Flagged proposals exceeding 1,800 characters under `POL-007-PROPOSAL-LENGTH-LIMIT`.
2. **Decision Node (`agent/nodes/decision.py`)**:
   - Automatically loads `minimum_fit_score: 0.75` from [agent/config.yaml](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/agent/config.yaml).
   - Evaluated an opportunity with `fit_score = 0.68` (which previously received a `"bid"` action under the old `0.60` threshold); immediately and deterministically flipped the outcome to `"skip"` with reason `"Fit score (0.68) is below minimum required threshold (0.75)."`.

### Verification Test Suite
Automated regression tests in [tests/unit/test_change_request.py](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/tests/unit/test_change_request.py) confirm all three behavioral shifts pass in 0.65s:
```bash
uv run pytest tests/unit/test_change_request.py -q
# Output: 3 passed in 0.65s
```

---

## 4. Key Takeaways

The strict separation of policy rules into YAML definitions and thresholds into declarative configuration enabled instant, zero-downtime policy enforcement. This validates that the system satisfies Assignment Part E and Requirement R8/R9 for operational change-readiness.

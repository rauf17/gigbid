# GigSim: Student-Built Marketplace Simulator

**Origin Notice**: `GIGSIM_ORIGIN=student-built`  
Because the instructor's GigSim was never distributed for AI-4016 GigBid, this module provides an independent, fully deterministic, student-built simulation server representing a freelance marketplace (e.g., Upwork).

---

## 1. Quickstart & Running

### Starting the Server
Run the FastAPI simulator on port 8081:
```bash
uv run uvicorn gigsim.app:app --port 8081
```

By default, SQLite database state is initialized under `gigsim/state/gigsim.db` (gitignored).

### Database Seeding & Reset
- **Via Make / CLI**:
  ```bash
  make seed
  # or directly:
  uv run python gigsim/seed.py
  ```
- **Via Admin Endpoint**:
  ```bash
  curl -X POST http://localhost:8081/admin/reset
  ```

---

## 2. Platform Architecture & Configuration

All platform rules, Connects tariffs, rate limits, and simulation parameters are configured in [seed/platform_rules.yaml](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/gigsim/seed/platform_rules.yaml). Platform updates are purely YAML edits without requiring code changes.

- **Initial Balance**: 150 Connects
- **Weekly Grant**: 80 Connects
- **Connects Tier Tariffs**:
  - Budget < $100: 4 Connects
  - Budget $100 - $599: 8 Connects
  - Budget $600 - $2,999: 12 Connects
  - Budget ≥ $3,000: 16 Connects
- **Rate Limit**: 30 requests/minute (sliding window, returns 429 with `Retry-After`)
- **Transient Fault Injection**: 3% simulated 500 errors (disabled in test mode via `GIGSIM_TESTING=1`)
- **Client Decision Engine Hook**: `client_llm: false` (deterministic mode active)

---

## 3. Full API Contract

### Authentication
If `GIGSIM_API_TOKEN` environment variable is set, all non-exempt endpoints require a Bearer token:
```http
Authorization: Bearer <GIGSIM_API_TOKEN>
```
`/health` is always exempt.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Returns simulator status, simulated time, connects balance, and active proposals. |
| `GET` | `/jobs` | Lists released jobs. Query params: `q`, `category`, `since`, `limit` (default 20), `cursor`. |
| `GET` | `/jobs/{id}` | Retrieves full details of a released job. Returns 404 if not released yet. |
| `GET` | `/clients/{id}` | Public client metrics (`company`, `industry`, `payment_verified`, `total_spent`, `hire_rate`, `avg_rating`, `jobs_posted`, `review_count`). Zero leakage of hidden preferences. |
| `GET` | `/connects/balance` | Returns available Connects balance, currency type, and weekly grant information. |
| `POST` | `/proposals` | Creates a proposal. Body: `{job_id, cover_letter, bid_amount, dry_run, screening_answers}`.<br>If `dry_run: true`, computes and returns Connects tariff and payload preview without spending Connects or persisting to DB. Normal mode creates a `draft`. |
| `POST` | `/proposals/{id}/submit` | Submits draft proposal. Requires `Idempotency-Key` header. Deducts Connects exactly once per key. Retries with the same key replay the cached response. |
| `GET` | `/proposals` | Lists submitted/draft proposals. Query param: `status`. |
| `GET` | `/conversations` | Lists active client conversations and latest message preview. |
| `GET` | `/conversations/{id}/messages` | Retrieves message history for a conversation. |
| `POST` | `/conversations/{id}/messages` | Sends a message to a client conversation. Accepts `Idempotency-Key` header. |
| `POST` | `/admin/tick` | Query param `n` (default 5). Releases `n` stream jobs, advances simulated time by 24 hours, and deterministically scores submitted proposals against client preferences. |
| `POST` | `/admin/reset` | Resets SQLite state, clears tables, and re-seeds initial 15 released jobs and 150 Connects. |

---

## 4. Client Decision Engine & Scoring Formula

When `/admin/tick` advances time, all proposals in `submitted` status are evaluated by a deterministic decision engine in [gigsim/clients.py](file:///c:/Users/AR/Desktop/Agentic_A2/gigbid/gigsim/clients.py).

### Deterministic Seeding
Evaluation is seeded per proposal ID:
$$\text{seed} = \text{int}\left(\text{SHA256}(\text{proposal\_id})[0:8], 16\right)$$
Evaluating the same proposal against the same client preferences always yields identical scores, status transitions, and generated messages.

### Scoring Breakdown
The composite proposal score $S \in [0.0, 1.0]$ is computed as:
$$S = \text{clamp}_{[0, 1]}\left(0.15 + S_{\text{overlap}} + S_{\text{spec}} + \Delta_{\text{generic}} + \Delta_{\text{budget}} + \Delta_{\text{speed}}\right)$$

1. **Must-Have Skills Overlap ($S_{\text{overlap}}$, weight 0.30)**:
   $$\text{overlap\_ratio} = \frac{|\text{matched skills in cover letter}|}{|\text{client.must\_have\_skills}|}$$
   $$S_{\text{overlap}} = \text{overlap\_ratio} \times 0.30$$

2. **Specificity & Metrics ($S_{\text{spec}}$, weight 0.25)**:
   - Project indicator regex: `project|pipeline|architecture|database|infrastructure|microservice|model|engine|system|dataset|platform|fastapi|react|postgres|docker`
   - Metric indicator regex: `\d+%|\$\d+|\d+\s*(ms|s|x|gb|tb|k|m|users|qps|req/s)|(reduced|increased|improved|scaled)\b.*\b\d+`
   - Base specificity:
     - Both project + metric present: $1.0$ ($0.25$ points)
     - Either project or metric: $0.5$ ($0.125$ points)
     - Neither: $0.1$ ($0.025$ points)
   - If `client.likes_metrics == True`: $+0.05$ bonus if metric present; $-0.10$ penalty if missing.
   - If specificity falls below `client.min_specificity`: $-0.10$ penalty.

3. **Generic Opener Penalty ($\Delta_{\text{generic}}$)**:
   - Scans for cliche patterns (`"i am excited to apply"`, `"dear sir"`, `"dear hiring manager"`, `"100% job success"`, `"hire me and i will get started"`, `"lowest price"`, `"24/7 support"`).
   - If generic opener is detected:
     - If `client.dislikes_generic_openers == True`: $-0.25$ penalty.
     - Otherwise: $-0.10$ penalty.
   - If no generic opener is detected: $+0.05$ bonus.

4. **Bid vs Budget Ceiling ($\Delta_{\text{budget}}$)**:
   - If $\text{bid} \le \text{client.budget\_ceiling}$: $+0.15$ bonus.
   - If $\text{bid} > \text{client.budget\_ceiling}$: progressive penalty:
     $$\Delta_{\text{budget}} = -0.25 \times \min\left(2.0, \frac{\text{bid} - \text{budget\_ceiling}}{\text{budget\_ceiling}}\right)$$

5. **Turnaround Speed ($\Delta_{\text{speed}}$)**:
   - Measured as $\Delta t = \text{proposal.submitted\_at} - \text{job.posted\_at}$:
     - $\Delta t \le 12$ hours: $+0.10$ bonus (rapid applicant)
     - $12 < \Delta t \le 36$ hours: $+0.05$ bonus
     - $36 < \Delta t \le 72$ hours: $0.00$ neutral
     - $\Delta t > 72$ hours: $-0.05$ penalty (late applicant)

### Probability Mapping & Outcome Sampling
The score $S$ is converted into unnormalized weights for each transition state:
- $w_{\text{ignored}} = \exp\left(3.2 \times (1.0 - S)\right)$
- $w_{\text{viewed}} = \exp\left(1.8 \times (1.0 - |S - 0.40|)\right)$
- $w_{\text{replied}} = \exp\left(2.8 \times S\right)$
- $w_{\text{interview}} = \exp\left(4.2 \times (S - 0.35)\right) \quad (\text{if } S \ge 0.30 \text{ else } 0.01)$
- $w_{\text{hired}} = \exp\left(5.5 \times (S - 0.60)\right) \quad (\text{if } S \ge 0.50 \text{ else } 0.001)$

Weights are normalized with softmax:
$$P(\text{outcome}_i) = \frac{w_i}{\sum_j w_j}$$
The deterministic RNG selects the outcome based on these probabilities.

### Template Generation
When an outcome is generated:
- **`ignored`**: Proposal archived without client response.
- **`viewed`**: Profile viewed; no message dispatched.
- **`replied`**: Dispatches either a requirement clarification question, a rate negotiation message, or (for scam postings) an off-platform diversion message (Telegram/WhatsApp/crypto).
- **`interview`**: Dispatches a technical interview scheduling invitation.
- **`hired`**: Dispatches contract award and milestone creation confirmation.

### Optional LLM Hook
The configuration parameter `simulation.client_llm: false` controls whether evaluation is delegated to an external LLM. It is strictly disabled and throws `NotImplementedError` if set to `true`, maintaining fast, 100% deterministic simulation for CI and testing.

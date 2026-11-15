import {
  MOCK_EVIDENCE,
  MOCK_JOBS,
  MOCK_PROPOSALS,
} from "./mock_data";

// In-memory mock store for interactive actions during session/tests
export const mockState = {
  jobs: [...MOCK_JOBS],
  proposals: { ...MOCK_PROPOSALS },
  profile: {
    persona_id: "ai_ml",
    email: "reviewer@gigbid.local",
    autonomy_mode: "supervised",
    budget_cap: 10000,
    saved_searches: ["LangGraph", "FastAPI", "LightGBM", "DuckDB"],
  },
  memories: [
    { id: "mem_001", key: "client_preference:client_enterprise_99", value: "Prefers Docker container deployments" },
    { id: "mem_002", key: "pricing:ai_ml", value: "Optimal hourly anchor $85-110/hr" },
  ],
  simTickCount: 0,
};

export function handleMockRequest<T>(path: string, options: RequestInit = {}): T {
  const method = (options.method || "GET").toUpperCase();

  // Auth & Profile
  if (path === "/auth/me" || path === "/api/auth/me") {
    return { id: "usr_mock", email: mockState.profile.email, persona_id: mockState.profile.persona_id } as T;
  }
  if (path === "/auth/login" || path === "/api/auth/login") {
    return { access_token: "mock_jwt_token_123", token_type: "bearer" } as T;
  }
  if (path === "/auth/logout" || path === "/api/auth/logout") {
    return { status: "ok", message: "Logged out" } as T;
  }
  if (path === "/profile" || path === "/api/profile") {
    if (method === "PUT" || method === "POST") {
      const body = JSON.parse((options.body as string) || "{}");
      if (body.persona_id) mockState.profile.persona_id = body.persona_id;
      if (body.autonomy_mode) mockState.profile.autonomy_mode = body.autonomy_mode;
      if (body.budget_cap) mockState.profile.budget_cap = body.budget_cap;
      return mockState.profile as T;
    }
    return mockState.profile as T;
  }

  // Jobs
  if (path.startsWith("/jobs") || path.startsWith("/api/jobs")) {
    const parts = path.split("/");
    const jobId = parts[parts.length - 1];
    if (jobId && jobId !== "jobs") {
      const j = mockState.jobs.find((x) => x.id === jobId) || mockState.jobs[0];
      return j as T;
    }
    return mockState.jobs as T;
  }

  // Approvals
  if (path.includes("/approvals") || path.includes("/api/approvals")) {
    const parts = path.split("/");
    const id = parts[parts.length - 1];

    if (method === "POST") {
      const body = JSON.parse((options.body as string) || "{}");
      const pId = id.includes(":") ? id.split(":")[1] : id;
      const prop = mockState.proposals[pId] || mockState.proposals["job_001"];

      if (body.action === "approve") {
        prop.status = "submitted";
        const job = mockState.jobs.find((j) => j.id === pId);
        if (job) job.status = "submitted";
        return { thread_id: id, status: "submitted", action_taken: "approve", message: "Approved" } as T;
      }
      if (body.action === "reject") {
        prop.status = "rejected";
        prop.rejection_reason = body.reason || "Rejected by user";
        const job = mockState.jobs.find((j) => j.id === pId);
        if (job) job.status = "lost";
        return { thread_id: id, status: "rejected", action_taken: "reject", message: "Rejected" } as T;
      }
      if (body.action === "edit") {
        const text = body.edited_text || "";
        const lower = text.toLowerCase();
        if (lower.includes("telegram") || lower.includes("whatsapp") || lower.includes("paypal") || lower.includes("crypto")) {
          return {
            thread_id: id,
            status: "blocked",
            action_taken: "edit",
            violations: ["Off-platform contact or payment prohibited by policy (POL-001/POL-002)."],
            message: "Edited proposal was blocked by compliance rules",
          } as T;
        }
        prop.cover_letter = text;
        return { thread_id: id, status: "awaiting_approval", action_taken: "edit", message: "Updated" } as T;
      }
    }

    // GET /approvals/{id}
    const pId = id.includes(":") ? id.split(":")[1] : id;
    const prop = mockState.proposals[pId] || mockState.proposals["job_001"];
    const job = mockState.jobs.find((j) => j.id === pId) || mockState.jobs[0];
    return {
      thread_id: `usr_mock:${pId}`,
      job_id: pId,
      status: prop.status,
      job_title: job.title,
      draft: {
        cover_letter: prop.cover_letter,
        proposed_rate: prop.proposed_rate,
        screening_answers: prop.screening_answers,
      },
      claim_evidence: (prop as any).claims || prop.evidence_items || [],
      evidence_store: MOCK_EVIDENCE,
      risk: { is_scam: job.scam_score > 0.5, scam_score: job.scam_score, client_trust_score: job.client_trust_score },
      price_rationale: { proposed_rate: prop.proposed_rate },
      dry_run: { connects_cost: 4 },
      critic_comments: { grounding: prop.critic_score },
    } as T;
  }

  // Proposals
  if (path.includes("/proposals") || path.includes("/api/proposals")) {
    const parts = path.split("/");
    const id = parts[parts.length - 1];

    if (method === "POST" && path.endsWith("/approve")) {
      const pId = parts[parts.length - 2];
      const prop = mockState.proposals[pId] || mockState.proposals["job_001"];
      prop.status = "submitted";
      const job = mockState.jobs.find((j) => j.id === pId);
      if (job) job.status = "submitted";
      return { status: "submitted", proposal: prop } as T;
    }

    if (method === "POST" && path.endsWith("/reject")) {
      const pId = parts[parts.length - 2];
      const body = JSON.parse((options.body as string) || "{}");
      const prop = mockState.proposals[pId] || mockState.proposals["job_001"];
      prop.status = "rejected";
      prop.rejection_reason = body.reason || "Rejected by user";
      const job = mockState.jobs.find((j) => j.id === pId);
      if (job) job.status = "lost";
      return { status: "rejected", reason: prop.rejection_reason } as T;
    }

    if (method === "PUT") {
      const body = JSON.parse((options.body as string) || "{}");
      const prop = mockState.proposals[id] || mockState.proposals["job_001"];
      if (body.cover_letter) {
        prop.cover_letter = body.cover_letter;
        const lower = body.cover_letter.toLowerCase();
        if (lower.includes("telegram") || lower.includes("whatsapp") || lower.includes("paypal") || lower.includes("crypto")) {
          prop.compliance_clean = false;
          prop.compliance_violations = ["Off-platform contact or payment prohibited by policy (POL-001/POL-002)."];
          return {
            status: "compliance_violation",
            violations: prop.compliance_violations,
            proposal: prop,
          } as T;
        } else {
          prop.compliance_clean = true;
          prop.compliance_violations = [];
        }
      }
      return prop as T;
    }

    // Pipeline response
    if (path.endsWith("/proposals") || path.endsWith("/api/proposals")) {
      return {
        drafted: [
          { thread_id: "usr_mock:job_001", job_id: "job_001", persona_id: "ai_ml", status: "drafted", bid_amount: 950 },
        ],
        submitted: [
          { thread_id: "usr_mock:job_002", job_id: "job_002", persona_id: "ai_ml", status: "submitted", bid_amount: 1200 },
        ],
        viewed: [],
        replied: [],
        interview: [],
        hired: [],
        lost: [],
      } as T;
    }

    return (mockState.proposals[id] || mockState.proposals["job_001"]) as T;
  }

  // Runs
  if (path.startsWith("/runs") || path.startsWith("/api/runs")) {
    if (method === "POST") {
      return { thread_id: "usr_mock:job_001", status: "running" } as T;
    }
    return {
      thread_id: "usr_mock:job_001",
      status: "awaiting_approval",
      is_awaiting_approval: true,
      current_node: "approval",
    } as T;
  }

  // Analytics
  if (path.startsWith("/analytics") || path.startsWith("/api/analytics")) {
    return {
      outcomes_by_category: [
        { category: "ai_ml", bids: 24, replies: 10, hires: 6, reply_rate: 0.41, hire_rate: 0.25 },
        { category: "fullstack", bids: 16, replies: 5, hires: 3, reply_rate: 0.31, hire_rate: 0.18 },
      ],
      connects_spent_vs_outcomes: [
        { category: "ai_ml", connects_spent: 96, proposals_submitted: 24, hires_won: 6 },
      ],
      cost_and_latency: [
        { model: "llama-3.3-70b-versatile", total_calls: 120, total_tokens: 45000, total_cost_usd: 0.045, avg_latency_ms: 850.0 },
      ],
      top_rejection_reasons: [
        { reason: "Budget mismatch / rate anchor low", count: 8, pct: 44 },
      ],
    } as T;
  }

  // Messages
  if (path.startsWith("/messages") || path.startsWith("/api/messages")) {
    if (path.includes("/suggestion")) {
      return {
        conversation_id: "conv_default",
        thread_id: "usr_mock:conv_default",
        status: "suggested",
        intent: "question",
        suggested_reply: "I have extensive experience with pgvector in PostgreSQL.",
        proposed_slots: [],
        is_awaiting_approval: true,
        compliance_passed: true,
        risk_flags: [],
        detail: "Generated suggestion",
      } as T;
    }
    return [
      {
        id: "msg_1",
        conversation_id: "conv_default",
        sender_id: "client_acme",
        sender_role: "client",
        text: "What is your experience deploying vector databases?",
        timestamp: new Date().toISOString(),
      },
    ] as T;
  }

  // Simulation tick
  if (path === "/sim/tick" || path === "/api/sim/tick") {
    mockState.simTickCount += 1;
    return { tick: mockState.simTickCount, advanced: true, new_events: 1 } as T;
  }

  // Memories
  if (path === "/memory" || path === "/api/memory") {
    if (method === "DELETE") {
      mockState.memories = [];
      return { success: true, cleared: true } as T;
    }
    return mockState.memories as T;
  }

  return {} as T;
}

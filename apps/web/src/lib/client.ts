import {
  MOCK_EVIDENCE,
  MOCK_JOBS,
  MOCK_PROPOSALS,
  MockEvidenceItem,
  MockJob,
  MockProposal,
} from "./mock_data";

const IS_MOCK = process.env.NEXT_PUBLIC_MOCK === "1";
const API_BASE = "";

// In-memory mock store for interactive actions during session/tests
const mockState = {
  jobs: [...MOCK_JOBS],
  proposals: { ...MOCK_PROPOSALS },
  profile: {
    persona_id: "ai_ml",
    email: "reviewer@gigbid.ai",
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

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (IS_MOCK) {
    return handleMockRequest<T>(path, options);
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      credentials: "include",
    });

    if (!res.ok) {
      if (res.status === 503) {
        throw new Error("SERVICE_DEGRADED");
      }
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Request failed with status ${res.status}`);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err.message === "SERVICE_DEGRADED") {
      throw err;
    }
    // Fallback to mock data if backend is offline in development
    return handleMockRequest<T>(path, options);
  }
}

function handleMockRequest<T>(path: string, options: RequestInit = {}): T {
  const method = (options.method || "GET").toUpperCase();

  // Auth & Profile
  if (path === "/auth/me" || path === "/api/auth/me") {
    return { email: mockState.profile.email, persona_id: mockState.profile.persona_id } as T;
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

  // Proposals & Approvals
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
        // Check for simulated compliance violation e.g. telegram, whatsapp, paypal
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

    return (mockState.proposals[id] || mockState.proposals["job_001"]) as T;
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

  // Default fallback
  return {} as T;
}

export const api = {
  auth: {
    me: () => apiFetch<{ email: string; persona_id: string }>("/api/auth/me"),
    login: (body: { email: string; password: string }) =>
      apiFetch<{ access_token: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    logout: () => apiFetch<{ success: boolean }>("/api/auth/logout", { method: "POST" }),
  },
  profile: {
    get: () => apiFetch<typeof mockState.profile>("/api/profile"),
    update: (body: Partial<typeof mockState.profile>) =>
      apiFetch<typeof mockState.profile>("/api/profile", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  },
  jobs: {
    list: () => apiFetch<MockJob[]>("/api/jobs"),
    get: (id: string) => apiFetch<MockJob>(`/api/jobs/${id}`),
  },
  proposals: {
    get: (jobId: string) => apiFetch<MockProposal>(`/api/proposals/${jobId}`),
    update: (jobId: string, body: { cover_letter: string }) =>
      apiFetch<{ status?: string; violations?: string[]; proposal: MockProposal }>(
        `/api/proposals/${jobId}`,
        { method: "PUT", body: JSON.stringify(body) }
      ),
    approve: (jobId: string) =>
      apiFetch<{ status: string; proposal: MockProposal }>(`/api/proposals/${jobId}/approve`, {
        method: "POST",
      }),
    reject: (jobId: string, reason: string) =>
      apiFetch<{ status: string; reason: string }>(`/api/proposals/${jobId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
  },
  sim: {
    tick: () => apiFetch<{ tick: number; advanced: boolean }>("/api/sim/tick", { method: "POST" }),
  },
  memory: {
    list: () => apiFetch<Array<{ id: string; key: string; value: string }>>("/api/memory"),
    clear: () => apiFetch<{ success: boolean }>("/api/memory", { method: "DELETE" }),
  },
  health: {
    check: async () => {
      try {
        const res = await fetch("/api/health");
        if (res.status === 503) return { degraded: true };
        return { degraded: false };
      } catch {
        return { degraded: false };
      }
    },
  },
};

import {
  ApprovalDecisionResponse,
  ApprovalDetail,
  AnalyticsResponse,
  JobDetail,
  JobSummary,
  MemoryItem,
  ProposalPipeline,
  UserProfile,
  UserResponse,
} from "./types";

export function isMockMode(): boolean {
  if (typeof window !== "undefined") {
    if ((window as any).__NEXT_PUBLIC_MOCK__ === true) return true;
    if (/(?:^|;\s*)NEXT_PUBLIC_MOCK=1/.test(document.cookie)) return true;
  }
  if (typeof process !== "undefined" && process.env) {
    const env = process.env;
    if (env["NEXT_PUBLIC_MOCK"] === "1" || env["MOCK"] === "1") {
      return true;
    }
  }
  return false;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function getAuthHeader(): Record<string, string> {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("gigbid_token");
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  }
  return {};
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (isMockMode()) {
    const { handleMockRequest } = await import("./mock_handler");
    return handleMockRequest<T>(path, options);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
      ...options.headers,
    },
    credentials: "include",
  });

  if (!res.ok) {
    if (res.status === 503) {
      throw new Error("SERVICE_DEGRADED");
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detailMsg = typeof err.detail === "object" ? JSON.stringify(err.detail) : err.detail;
    throw new Error(detailMsg || `Request failed with status ${res.status}`);
  }

  return (await res.json()) as T;
}

export const api = {
  auth: {
    me: () => apiFetch<UserResponse>("/api/auth/me"),
    login: async (body: { email: string; password: string }) => {
      const res = await apiFetch<{ access_token: string; token_type: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (typeof window !== "undefined" && res.access_token) {
        localStorage.setItem("gigbid_token", res.access_token);
      }
      return res;
    },
    logout: async () => {
      try {
        await apiFetch<{ status: string; message: string }>("/api/auth/logout", { method: "POST" });
      } finally {
        if (typeof window !== "undefined") {
          localStorage.removeItem("gigbid_token");
        }
      }
      return { success: true };
    },
  },
  profile: {
    get: () => apiFetch<UserProfile>("/api/profile"),
    update: (body: Partial<UserProfile>) =>
      apiFetch<UserProfile>("/api/profile", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  },
  jobs: {
    list: (params?: { category?: string; status?: string; min_fit?: number; limit?: number }) => {
      const searchParams = new URLSearchParams();
      if (params?.category) searchParams.set("category", params.category);
      if (params?.status) searchParams.set("status", params.status);
      if (params?.min_fit !== undefined) searchParams.set("min_fit", String(params.min_fit));
      if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
      const qs = searchParams.toString();
      return apiFetch<JobSummary[]>(`/api/jobs${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => apiFetch<JobDetail>(`/api/jobs/${id}`),
    skip: (id: string, reason: string) =>
      apiFetch<{ status: string; message: string }>(`/api/jobs/${id}/skip`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
  },
  runs: {
    create: (body: { job_id: string; persona_id?: string }) =>
      apiFetch<{ thread_id: string; status: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (threadId: string) =>
      apiFetch<{
        thread_id: string;
        status: string;
        state_summary: Record<string, any>;
        current_node: string | null;
        is_awaiting_approval: boolean;
      }>(`/api/runs/${threadId}`),
    trace: (threadId: string) =>
      apiFetch<{ thread_id: string; trace_id: string | null; trace_url: string | null; traces: any[] }>(
        `/api/runs/${threadId}/trace`
      ),
  },
  approvals: {
    list: () => apiFetch<Array<{ thread_id: string; checkpoint_id: string | null; payload: any }>>("/api/approvals"),
    get: (threadId: string) => apiFetch<ApprovalDetail>(`/api/approvals/${threadId}`),
    decide: (
      threadId: string,
      decision: { action: "approve" | "edit" | "reject"; edited_text?: string; reason?: string }
    ) =>
      apiFetch<ApprovalDecisionResponse>(`/api/approvals/${threadId}`, {
        method: "POST",
        body: JSON.stringify(decision),
      }),
  },
  proposals: {
    pipeline: () => apiFetch<ProposalPipeline>("/api/proposals"),
    get: (jobId: string) => apiFetch<any>(`/api/proposals/${jobId}`),
    approve: (jobId: string) =>
      apiFetch<any>(`/api/approvals/${jobId}`, {
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      }),
    reject: (jobId: string, reason: string) =>
      apiFetch<any>(`/api/approvals/${jobId}`, {
        method: "POST",
        body: JSON.stringify({ action: "reject", reason }),
      }),
    update: (jobId: string, body: { cover_letter: string }) =>
      apiFetch<any>(`/api/approvals/${jobId}`, {
        method: "POST",
        body: JSON.stringify({ action: "edit", edited_text: body.cover_letter }),
      }),
  },
  messages: {
    list: (convId = "conv_default") =>
      apiFetch<any[]>(`/api/messages?conversation_id=${convId}`),
    reply: (convId: string, text: string) =>
      apiFetch<any>(`/api/messages/${convId}/reply`, {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    suggestion: (convId: string) =>
      apiFetch<any>(`/api/messages/${convId}/suggestion`),
    approve: (convId: string, body: { action: "approve" | "edit" | "reject"; edited_text?: string }) =>
      apiFetch<any>(`/api/messages/${convId}/approve`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
  analytics: {
    get: () => apiFetch<AnalyticsResponse>("/api/analytics"),
  },
  memory: {
    list: (namespace?: string) =>
      apiFetch<MemoryItem[]>(`/api/memory${namespace ? `?namespace=${namespace}` : ""}`),
    delete: (id: string, namespace = "style") =>
      apiFetch<{ status: string; message: string }>(`/api/memory/${id}?namespace=${namespace}`, {
        method: "DELETE",
      }),
    clear: () => apiFetch<{ success: boolean; cleared: boolean }>("/api/memory", { method: "DELETE" }),
  },
  sim: {
    tick: () => apiFetch<{ tick: number; advanced: boolean }>("/api/sim/tick", { method: "POST" }),
  },
  health: {
    check: async () => {
      if (isMockMode()) return { degraded: false };
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.status === 503) return { degraded: true };
        return { degraded: false };
      } catch {
        return { degraded: false };
      }
    },
  },
};

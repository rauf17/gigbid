export interface JobSummary {
  id: string;
  title: string;
  description?: string;
  client_name?: string;
  client_id?: string;
  client_country?: string | null;
  category: string;
  budget?: number | null;
  budget_min?: number | null;
  budget_max?: number | null;
  budget_type?: string;
  connects_cost: number;
  fit_score?: number | null;
  risk_score?: number | null;
  client_trust_score?: number | null;
  risk_badges?: string[];
  recommended_action?: string;
  quote?: number | null;
  status: string; // "not_analysed" | "new" | "running" | "awaiting_approval" | "submitted" | "skipped"
  skip_reason?: string | null;
  is_scam?: boolean;
  scam_reason?: string | null;
  created_at?: string | null;
  posted_at?: string | null;
}

export interface JobDetail {
  id: string;
  title: string;
  description: string;
  skills: string[];
  budget?: number | null;
  budget_min?: number | null;
  budget_max?: number | null;
  budget_type?: string;
  connects_cost: number;
  client_name: string;
  client_id?: string | null;
  client_country?: string | null;
  category: string;
  status?: string;
  posted_at?: string | null;
  risk_report?: Record<string, any>;
  requirement_evidence_matrix?: Array<Record<string, any>>;
  price_rationale?: Record<string, any>;
  decision_reasoning?: string | Record<string, any>;
  last_run?: Record<string, any> | null;
}

export interface EvidenceItem {
  id: string;
  title?: string;
  text: string;
  metric?: string | null;
  score?: number;
  skills?: string[];
  type?: string;
  source?: string;
  project?: string;
  outcome?: string;
}

export interface ApprovalDetail {
  thread_id: string;
  checkpoint_id?: string | null;
  job_id: string;
  job_title: string;
  draft: {
    cover_letter: string;
    screening_answers?: Array<{ question: string; answer: string }>;
    claims?: Array<{ text: string; evidence_ids: string[] }>;
    proposed_rate?: number;
  };
  claim_evidence?: Array<{
    claim?: string;
    text?: string;
    status?: string;
    evidence_ids?: string[];
    rationale?: string;
  }>;
  evidence_store?: Record<string, EvidenceItem>;
  risk?: Record<string, any>;
  price_rationale?: Record<string, any>;
  dry_run?: Record<string, any>;
  critic_comments?: Record<string, any> | null;
  compliance_comments?: Record<string, any> | null;
}

export interface ApprovalDecisionResponse {
  thread_id: string;
  status: string;
  action_taken: string;
  violations?: string[];
  message: string;
}

export interface ProposalItem {
  thread_id: string;
  job_id: string;
  persona_id: string;
  status: string;
  bid_amount?: number | null;
  proposal_text?: string | null;
  created_at?: string | null;
}

export interface ProposalPipeline {
  drafted: ProposalItem[];
  submitted: ProposalItem[];
  viewed: ProposalItem[];
  replied: ProposalItem[];
  interview: ProposalItem[];
  hired: ProposalItem[];
  lost: ProposalItem[];
}

export interface AnalyticsResponse {
  outcomes_by_category: Array<{
    category: string;
    bids: number;
    replies: number;
    hires: number;
    reply_rate: number;
    hire_rate: number;
  }>;
  connects_spent_vs_outcomes: Array<{
    category: string;
    connects_spent: number;
    proposals_submitted: number;
    hires_won: number;
  }>;
  cost_and_latency: Array<{
    model: string;
    total_calls: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_latency_ms: number;
  }>;
  top_rejection_reasons: Array<{
    reason: string;
    count: number;
    pct?: number;
  }>;
}

export interface UserResponse {
  id: string;
  email: string;
  persona_id: string;
  created_at?: string | null;
}

export interface UserProfile {
  persona_id: string;
  autonomy_mode: string;
  budget_cap: number;
  saved_searches: string[];
}

export interface MemoryItem {
  id: string;
  key: string;
  value: string;
  created_at?: string;
}

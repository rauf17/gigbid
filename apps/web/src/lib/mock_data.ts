export interface MockEvidenceItem {
  id: string;
  title: string;
  skills: string[];
  metric?: string;
  text: string;
  score: number;
}

export interface MockJob {
  id: string;
  title: string;
  client_id: string;
  client_trust_score: number;
  category: string;
  budget_min: number;
  budget_max: number;
  currency: string;
  description: string;
  fit_score: number;
  risk_level: "low" | "medium" | "high";
  scam_score: number;
  status: "discovered" | "analyzing" | "drafting" | "awaiting_review" | "submitted" | "won" | "lost";
  requirements: string[];
  evidence_ids: string[];
  created_at: string;
}

export interface MockProposal {
  id: string;
  job_id: string;
  cover_letter: string;
  proposed_rate: number;
  status: "draft" | "approved" | "rejected" | "submitted";
  rejection_reason?: string;
  compliance_clean: boolean;
  compliance_violations: string[];
  evidence_items: MockEvidenceItem[];
  screening_answers: { question: string; answer: string }[];
  critic_score: number;
}

export const MOCK_EVIDENCE: Record<string, MockEvidenceItem> = {
  "ai_ml_cs_cs_aiml_001": {
    id: "ai_ml_cs_cs_aiml_001",
    title: "LightGBM Demand Forecasting Engine",
    skills: ["Python", "LightGBM", "PostgreSQL", "Docker", "FastAPI"],
    metric: "98% forecasting accuracy, 30% waste reduction",
    text: "Engineered scalable time-series demand forecasting architecture processing 10M daily events with sub-50ms inference latency.",
    score: 0.94,
  },
  "fullstack_cs_002": {
    id: "fullstack_cs_002",
    title: "Next.js & FastAPI Collaborative Workspace",
    skills: ["Next.js", "TypeScript", "FastAPI", "Tailwind CSS", "PostgreSQL"],
    metric: "40% reduction in page load latency",
    text: "Architected modern responsive web interface with Server-Sent Events, real-time sync, and granular role-based tenant isolation.",
    score: 0.89,
  },
  "data_analyst_cs_003": {
    id: "data_analyst_cs_003",
    title: "Automated Financial Reconciliation Dashboard",
    skills: ["Python", "DuckDB", "Pandas", "Streamlit", "SQL"],
    metric: "12 hours saved per week on audit prep",
    text: "Built automated data ingestion pipeline reconciling multi-currency ledger discrepancies with instant anomaly alerting.",
    score: 0.91,
  },
};

export const MOCK_JOBS: MockJob[] = [
  {
    id: "job_001",
    title: "Production Time-Series Forecasting Pipeline with LightGBM",
    client_id: "client_enterprise_99",
    client_trust_score: 0.96,
    category: "ai_ml",
    budget_min: 3500,
    budget_max: 5000,
    currency: "USD",
    description: "Looking for an expert to construct an end-to-end LightGBM forecasting service in Python, containerized with Docker, deployed with FastAPI, and integrated with Postgres.",
    fit_score: 0.94,
    risk_level: "low",
    scam_score: 0.02,
    status: "awaiting_review",
    requirements: [
      "LightGBM model training and hyperparameter optimization",
      "FastAPI endpoint deployment with Pydantic payload validation",
      "Containerization using multi-stage Docker builds",
    ],
    evidence_ids: ["ai_ml_cs_cs_aiml_001"],
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
  },
  {
    id: "job_002",
    title: "Next.js 14 Dashboard with Real-time SSE Streams",
    client_id: "client_fintech_42",
    client_trust_score: 0.88,
    category: "fullstack",
    budget_min: 4000,
    budget_max: 6000,
    currency: "USD",
    description: "Build an executive analytics workspace in Next.js 14 App Router connected to FastAPI backend via Server-Sent Events with Tailwind CSS.",
    fit_score: 0.89,
    risk_level: "low",
    scam_score: 0.01,
    status: "awaiting_review",
    requirements: [
      "Next.js 14 App Router and TypeScript",
      "Server-Sent Events for streaming updates",
      "Accessible Tailwind CSS responsive UI",
    ],
    evidence_ids: ["fullstack_cs_002"],
    created_at: new Date(Date.now() - 3600000 * 5).toISOString(),
  },
  {
    id: "job_003",
    title: "Financial ETL Pipeline & Anomaly Dashboard in DuckDB",
    client_id: "client_retail_12",
    client_trust_score: 0.92,
    category: "data_analyst",
    budget_min: 2500,
    budget_max: 4000,
    currency: "USD",
    description: "Construct automated reconciliation queries in DuckDB and Python to audit millions of merchant ledger rows weekly.",
    fit_score: 0.91,
    risk_level: "low",
    scam_score: 0.03,
    status: "drafting",
    requirements: [
      "DuckDB and SQL performance tuning",
      "Automated outlier detection algorithms",
    ],
    evidence_ids: ["data_analyst_cs_003"],
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
  },
  {
    id: "job_004",
    title: "Urgent: Telegram Crypto Arbitrage Bot ($10k guaranteed)",
    client_id: "client_sketchy_00",
    client_trust_score: 0.15,
    category: "ai_ml",
    budget_min: 8000,
    budget_max: 10000,
    currency: "USD",
    description: "Contact me on telegram @fast_crypto_money immediately for off-platform payment. 100% guaranteed results.",
    fit_score: 0.20,
    risk_level: "high",
    scam_score: 0.98,
    status: "discovered",
    requirements: ["Scam proposal attempt"],
    evidence_ids: [],
    created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
  },
];

export const MOCK_PROPOSALS: Record<string, MockProposal> = {
  "job_001": {
    id: "prop_001",
    job_id: "job_001",
    cover_letter: `Your project requires a robust time-series forecasting service with LightGBM, packaged cleanly for production.

I previously engineered an automated forecasting pipeline achieving 98% forecasting accuracy and 30% waste reduction [E:ai_ml_cs_cs_aiml_001]. In that deployment, we built asynchronous FastAPI ingestion routes with strict Pydantic schemas and orchestrated sub-50ms model inferencing.

For your system, I propose:
1. Data Pipeline: Asynchronous feature extraction with PostgreSQL and automated lag feature generation.
2. Model Architecture: LightGBM regressor with cross-validated hyperparameter tuning.
3. Production Packaging: Multi-stage Docker container with health probes and Prometheus metrics.

I am ready to establish the baseline pipeline within week 1.`,
    proposed_rate: 4200,
    status: "draft",
    compliance_clean: true,
    compliance_violations: [],
    evidence_items: [MOCK_EVIDENCE["ai_ml_cs_cs_aiml_001"]],
    screening_answers: [
      {
        question: "How do you handle feature drift in production time-series models?",
        answer: "By setting up automated Kolmogorov-Smirnov statistical tests on daily inference batches to alert on distribution shift."
      }
    ],
    critic_score: 0.92,
  },
  "job_002": {
    id: "prop_002",
    job_id: "job_002",
    cover_letter: `I can deliver the Next.js 14 App Router dashboard with Server-Sent Events tailored to your FastAPI endpoints.

In a recent collaborative workspace, I architected a high-throughput UI achieving a 40% reduction in page load latency [E:fullstack_cs_002]. The architecture utilizes React Server Components alongside real-time SSE event consumption.

Key milestones:
1. Next.js 14 App Router scaffolding with clean Tailwind CSS design system.
2. Resilient SSE subscription client with exponential reconnect backoff.
3. End-to-end type safety generated from OpenAPI specifications.

Looking forward to discussing the schema and layout specifics.`,
    proposed_rate: 5200,
    status: "draft",
    compliance_clean: true,
    compliance_violations: [],
    evidence_items: [MOCK_EVIDENCE["fullstack_cs_002"]],
    screening_answers: [],
    critic_score: 0.90,
  },
};

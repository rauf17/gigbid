"use client";

import React, { useEffect, useState } from "react";
import { JobSummary } from "@/lib/types";
import { api } from "@/lib/client";

export default function InboxPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [filter, setFilter] = useState<"all" | "high_match" | "review" | "not_analysed">("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"posted" | "fit" | "budget">("posted");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzingIds, setAnalyzingIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.jobs.list();
      setJobs(res);
    } catch (err: any) {
      setError(err.message || "Failed to load opportunities from marketplace API");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyse(jobId: string) {
    setAnalyzingIds((prev) => ({ ...prev, [jobId]: true }));
    try {
      await api.runs.create({ job_id: jobId });
      // Update local status to running
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: "running" } : j))
      );
      // Wait briefly and re-fetch to reflect state transition
      setTimeout(() => {
        loadJobs();
        setAnalyzingIds((prev) => ({ ...prev, [jobId]: false }));
      }, 2500);
    } catch (err: any) {
      alert(`Failed to start analysis run: ${err.message}`);
      setAnalyzingIds((prev) => ({ ...prev, [jobId]: false }));
    }
  }

  const filteredJobs = jobs
    .filter((j) => {
      if (filter === "high_match") return (j.fit_score ?? 0) >= 0.85;
      if (filter === "review") return j.status === "awaiting_approval" || j.status === "awaiting_review";
      if (filter === "not_analysed") return j.status === "not_analysed" || j.fit_score == null;
      return true;
    })
    .filter((j) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        j.title.toLowerCase().includes(q) ||
        (j.description && j.description.toLowerCase().includes(q)) ||
        (j.client_name && j.client_name.toLowerCase().includes(q)) ||
        (j.client_id && j.client_id.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      if (sort === "fit") {
        return (b.fit_score ?? -1) - (a.fit_score ?? -1);
      }
      if (sort === "budget") {
        const bBudget = b.budget_max ?? b.budget ?? 0;
        const aBudget = a.budget_max ?? a.budget ?? 0;
        return bBudget - aBudget;
      }
      // default: posted time / id
      const bTime = b.posted_at || b.created_at || "";
      const aTime = a.posted_at || a.created_at || "";
      return bTime.localeCompare(aTime);
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Opportunity Inbox</h1>
          <p className="text-xs text-slate-500">
            Autonomous market ingestion, scam filtering, and calibrated fit matching.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            data-testid="inbox-search-input"
            placeholder="Search jobs, skills, clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-xs px-3 py-1.5 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 w-48 sm:w-56"
          />

          <select
            value={sort}
            onChange={(e: any) => setSort(e.target.value)}
            className="text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white outline-none text-slate-700"
          >
            <option value="posted">Newest Posted</option>
            <option value="fit">Highest Fit</option>
            <option value="budget">Highest Budget</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 bg-white p-1 rounded-lg border border-slate-200 text-xs">
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1 rounded-md transition-colors ${
            filter === "all" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          All Opportunities ({jobs.length})
        </button>
        <button
          onClick={() => setFilter("high_match")}
          className={`px-3 py-1 rounded-md transition-colors ${
            filter === "high_match" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Strong Match (&gt;85%)
        </button>
        <button
          onClick={() => setFilter("review")}
          className={`px-3 py-1 rounded-md transition-colors ${
            filter === "review" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Awaiting Review
        </button>
        <button
          onClick={() => setFilter("not_analysed")}
          className={`px-3 py-1 rounded-md transition-colors ${
            filter === "not_analysed" ? "bg-slate-100 font-semibold text-slate-800" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Not Analysed
        </button>
      </div>

      {error && (
        <div data-testid="inbox-error-state" className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between text-xs text-rose-800">
          <div>
            <span className="font-semibold">Failed to fetch live marketplace jobs:</span> {error}
          </div>
          <button
            onClick={loadJobs}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white font-medium rounded-lg text-xs transition-colors shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-400">Loading opportunities from live API...</div>
      ) : filteredJobs.length === 0 ? (
        <div className="py-12 text-center text-xs text-slate-400 bg-white rounded-xl border border-slate-200">
          No opportunities found matching active filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredJobs.map((job) => {
            const isAnalysed = job.fit_score != null || job.status === "awaiting_approval" || job.status === "submitted" || job.status === "skipped";
            const isScam = Boolean(job.is_scam);
            const isAwaitingApproval = job.status === "awaiting_approval" || job.status === "awaiting_review";
            const isRunning = job.status === "running" || analyzingIds[job.id];
            const isSkipped = job.status === "skipped";
            const isSubmitted = job.status === "submitted";

            const clientIdentifier = job.client_id || job.client_name || "Confidential";
            const budgetDisplay =
              job.budget_min != null && job.budget_max != null
                ? `$${job.budget_min.toLocaleString()} – $${job.budget_max.toLocaleString()}`
                : job.budget != null
                ? `$${job.budget.toLocaleString()}`
                : "Budget negotiable";

            return (
              <div
                key={job.id}
                data-testid={`job-card-${job.id}`}
                className={`bg-white border rounded-xl p-5 shadow-sm transition-all hover:shadow-md ${
                  isScam ? "border-rose-200 bg-rose-50/20" : "border-slate-200"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        {job.category}
                      </span>

                      {!isAnalysed && !isRunning && (
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-500 font-medium">
                          Not analysed
                        </span>
                      )}

                      {isRunning && (
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-blue-100 text-blue-700 font-semibold animate-pulse">
                          Running analysis...
                        </span>
                      )}

                      {isScam && (
                        <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-rose-100 text-rose-700">
                          🚨 Scam Detected {job.scam_reason ? `(${job.scam_reason})` : ""}
                        </span>
                      )}

                      {isAnalysed && job.client_trust_score != null && (
                        <span className="text-xs text-emerald-600 font-medium">
                          Trust: {(job.client_trust_score * 100).toFixed(0)}%
                        </span>
                      )}

                      <span className="text-xs text-slate-400 font-mono">Client: {clientIdentifier}</span>
                      {job.client_country && (
                        <span className="text-xs text-slate-400">({job.client_country})</span>
                      )}
                      {(job.posted_at || job.created_at) && (
                        <span className="text-[11px] text-slate-400">
                          • {new Date(job.posted_at || job.created_at || "").toLocaleDateString()}
                        </span>
                      )}
                    </div>

                    <a
                      href={`/jobs/${job.id}`}
                      className="text-sm font-semibold text-slate-900 hover:text-blue-600 transition-colors block"
                    >
                      {job.title}
                    </a>

                    {job.description && (
                      <p className="text-xs text-slate-600 line-clamp-2 max-w-3xl">
                        {job.description}
                      </p>
                    )}

                    {isSkipped && job.skip_reason && (
                      <div className="text-[11px] text-slate-500 italic bg-slate-50 p-1.5 rounded border border-slate-100">
                        Skipped reason: {job.skip_reason}
                      </div>
                    )}
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0">
                    <div className="text-right">
                      <div className="text-sm font-bold text-slate-900">{budgetDisplay}</div>
                      {isAnalysed && job.fit_score != null ? (
                        <div className="text-[11px] font-medium text-emerald-700">
                          Fit Match: {(job.fit_score * 100).toFixed(0)}%
                        </div>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2 mt-2">
                      <a
                        href={`/jobs/${job.id}`}
                        className="px-3 py-1.5 text-xs font-medium border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                      >
                        Inspect
                      </a>

                      {!isAnalysed && !isRunning && (
                        <button
                          data-testid={`analyse-job-button-${job.id}`}
                          onClick={() => handleAnalyse(job.id)}
                          className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors"
                        >
                          Analyse
                        </button>
                      )}

                      {isRunning && (
                        <a
                          href={`/runs/${job.id}`}
                          className="px-3 py-1.5 text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 rounded-lg shadow-sm transition-colors"
                        >
                          View Run →
                        </a>
                      )}

                      {isAwaitingApproval && (
                        <a
                          href={`/studio/${job.id}`}
                          data-testid={`bid-studio-link-${job.id}`}
                          className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors"
                        >
                          Open Studio →
                        </a>
                      )}

                      {isSubmitted && (
                        <span className="px-2.5 py-1 text-[11px] font-semibold bg-emerald-100 text-emerald-800 rounded-lg">
                          Submitted
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

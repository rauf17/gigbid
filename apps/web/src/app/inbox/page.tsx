"use client";

import React, { useEffect, useState } from "react";
import { MockJob } from "@/lib/mock_data";
import { api } from "@/lib/client";

export default function InboxPage() {
  const [jobs, setJobs] = useState<MockJob[]>([]);
  const [filter, setFilter] = useState<"all" | "high_match" | "review">("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.jobs.list().then((res) => {
      setJobs(res);
      setLoading(false);
    });
  }, []);

  const filteredJobs = jobs.filter((j) => {
    if (filter === "high_match") return j.fit_score >= 0.85;
    if (filter === "review") return j.status === "awaiting_review";
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Opportunity Inbox</h1>
          <p className="text-xs text-slate-500">Autonomous market ingestion, scam filtering, and calibrated fit matching.</p>
        </div>

        <div className="flex items-center gap-1 bg-white p-1 rounded-lg border border-slate-200 text-xs">
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
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-400">Loading opportunities...</div>
      ) : filteredJobs.length === 0 ? (
        <div className="py-12 text-center text-xs text-slate-400 bg-white rounded-xl border border-slate-200">
          No opportunities found matching active filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredJobs.map((job) => {
            const isScam = job.scam_score > 0.50;
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
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        {job.category}
                      </span>
                      {isScam && (
                        <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-rose-100 text-rose-700">
                          🚨 Scam Detected ({(job.scam_score * 100).toFixed(0)}%)
                        </span>
                      )}
                      <span className="text-xs text-slate-400">Client: {job.client_id}</span>
                      <span className="text-xs text-emerald-600 font-medium">
                        Trust: {(job.client_trust_score * 100).toFixed(0)}%
                      </span>
                    </div>

                    <a
                      href={`/jobs/${job.id}`}
                      className="text-sm font-semibold text-slate-900 hover:text-blue-600 transition-colors block"
                    >
                      {job.title}
                    </a>

                    <p className="text-xs text-slate-600 line-clamp-2 max-w-3xl">
                      {job.description}
                    </p>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0">
                    <div className="text-right">
                      <div className="text-sm font-bold text-slate-900">
                        ${job.budget_min.toLocaleString()} – ${job.budget_max.toLocaleString()}
                      </div>
                      <div className="text-[11px] font-medium text-emerald-700">
                        Fit Match: {(job.fit_score * 100).toFixed(0)}%
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mt-2">
                      <a
                        href={`/jobs/${job.id}`}
                        className="px-3 py-1.5 text-xs font-medium border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                      >
                        Inspect
                      </a>
                      <a
                        href={`/studio/${job.id}`}
                        data-testid={`bid-studio-link-${job.id}`}
                        className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors"
                      >
                        Open Studio →
                      </a>
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

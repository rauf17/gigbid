"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { JobDetail } from "@/lib/types";
import { api } from "@/lib/client";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = (params?.id as string) || "job_001";
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingRun, setStartingRun] = useState(false);

  useEffect(() => {
    loadJob();
  }, [jobId]);

  async function loadJob() {
    setLoading(true);
    setError(null);
    try {
      const j = await api.jobs.get(jobId);
      setJob(j);
    } catch (err: any) {
      setError(err.message || "Failed to load job details from live API");
    } finally {
      setLoading(false);
    }
  }

  async function handleStartRun() {
    setStartingRun(true);
    try {
      const res = await api.runs.create({ job_id: jobId });
      router.push(`/runs/${res.thread_id || jobId}`);
    } catch (err: any) {
      alert(`Failed starting run: ${err.message}`);
      setStartingRun(false);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-400">Loading opportunity details...</div>;
  }

  if (error || !job) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between">
          <div>
            <span className="font-semibold">Error loading job {jobId}:</span> {error || "Job not found"}
          </div>
          <button
            onClick={loadJob}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs"
          >
            Retry
          </button>
        </div>
        <a href="/inbox" className="text-xs text-blue-600 hover:text-blue-700">← Back to Inbox</a>
      </div>
    );
  }

  const budgetDisplay =
    job.budget_min != null && job.budget_max != null
      ? `$${job.budget_min.toLocaleString()} – $${job.budget_max.toLocaleString()}`
      : job.budget != null
      ? `$${job.budget.toLocaleString()}`
      : "Negotiable";

  const isAwaitingReview = job.last_run?.status === "awaiting_approval";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <a href="/inbox" className="hover:text-slate-800">← Back to Inbox</a>
        <span>/</span>
        <span className="font-mono">{job.id}</span>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-slate-100 pb-5">
          <div className="space-y-1">
            <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-semibold">
              {job.category}
            </span>
            <h1 className="text-xl font-bold text-slate-900 mt-1">{job.title}</h1>
            <p className="text-xs text-slate-500">
              Client: <span className="font-mono font-medium">{job.client_id || job.client_name}</span>
              {job.client_country && <span> • Country: {job.client_country}</span>}
              {job.posted_at && <span> • Posted: {new Date(job.posted_at).toLocaleDateString()}</span>}
            </p>
          </div>

          <div className="sm:text-right shrink-0 space-y-2">
            <div className="text-lg font-bold text-slate-900">{budgetDisplay}</div>
            <div className="text-xs text-slate-500">Connects: {job.connects_cost}</div>

            {isAwaitingReview ? (
              <a
                href={`/studio/${job.id}`}
                className="inline-block px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all"
              >
                Review in Proposal Studio →
              </a>
            ) : (
              <button
                onClick={handleStartRun}
                disabled={startingRun}
                className="inline-block px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all disabled:opacity-50"
              >
                {startingRun ? "Starting Graph Run..." : "Generate Bid (Run Pipeline) →"}
              </button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Job Description</h2>
          <div className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-100 whitespace-pre-wrap">
            {job.description}
          </div>
        </div>

        {job.skills && job.skills.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Required Skills & Capabilities</h2>
            <div className="flex flex-wrap gap-2">
              {job.skills.map((skill, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 text-xs bg-slate-100 text-slate-700 rounded-md font-medium border border-slate-200"
                >
                  ✓ {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {job.last_run && (
          <div className="space-y-3 pt-3 border-t border-slate-100">
            <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Latest Graph Execution</h2>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-xs space-y-1">
              <div><span className="font-semibold text-slate-700">Thread:</span> <span className="font-mono">{job.last_run.thread_id}</span></div>
              <div><span className="font-semibold text-slate-700">Status:</span> <span className="font-mono uppercase text-blue-700 font-semibold">{job.last_run.status}</span></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

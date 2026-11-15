"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { MockJob } from "@/lib/mock_data";
import { api } from "@/lib/client";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = (params?.id as string) || "job_001";
  const [job, setJob] = useState<MockJob | null>(null);

  useEffect(() => {
    api.jobs.get(jobId).then((j) => setJob(j));
  }, [jobId]);

  if (!job) {
    return <div className="py-12 text-center text-xs text-slate-400">Loading opportunity details...</div>;
  }

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
              Posted by <span className="font-mono font-medium">{job.client_id}</span> • Trust Score:{" "}
              <span className="text-emerald-700 font-semibold">{(job.client_trust_score * 100).toFixed(0)}%</span>
            </p>
          </div>

          <div className="sm:text-right shrink-0">
            <div className="text-lg font-bold text-slate-900">
              ${job.budget_min.toLocaleString()} – ${job.budget_max.toLocaleString()}
            </div>
            <div className="text-xs font-semibold text-emerald-700">
              Fit Score: {(job.fit_score * 100).toFixed(0)}% Match
            </div>
            <a
              href={`/studio/${job.id}`}
              className="mt-3 inline-block px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all"
            >
              Draft & Review Proposal →
            </a>
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Job Description</h2>
          <div className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-100">
            {job.description}
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Extracted Requirements</h2>
          <ul className="space-y-2">
            {job.requirements.map((req, i) => (
              <li key={i} className="text-xs text-slate-700 flex items-start gap-2">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>{req}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Retrieved Portfolio Evidence</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {job.evidence_ids.map((eid) => (
              <div key={eid} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                <div className="text-[11px] font-mono text-blue-700 font-semibold">{eid}</div>
                <div className="text-xs text-slate-600 mt-1">Grounding citation ready for proposal insertion.</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

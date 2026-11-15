"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { MockJob, MockProposal } from "@/lib/mock_data";
import { api } from "@/lib/client";
import { EvidenceHover } from "@/components/EvidenceHover";
import { ApprovalPanel } from "@/components/ApprovalPanel";

export default function StudioPage() {
  const params = useParams();
  const jobId = (params?.id as string) || "job_001";

  const [job, setJob] = useState<MockJob | null>(null);
  const [proposal, setProposal] = useState<MockProposal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.jobs.get(jobId), api.proposals.get(jobId)]).then(([j, p]) => {
      setJob(j);
      setProposal(p);
      setLoading(false);
    });
  }, [jobId]);

  if (loading || !job || !proposal) {
    return <div className="py-12 text-center text-xs text-slate-400">Loading proposal studio...</div>;
  }

  // Render text replacing [E:...] with EvidenceHover interactive pills
  function renderFormattedProposal(text: string) {
    const parts = text.split(/(\[(?:E:)?[a-zA-Z0-9_\-]+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[(?:E:)?([a-zA-Z0-9_\-]+)\]$/);
      if (match) {
        return (
          <EvidenceHover key={idx} evidenceId={match[1]}>
            {part}
          </EvidenceHover>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <a href="/inbox" className="hover:text-slate-800">Inbox</a>
            <span>/</span>
            <a href={`/jobs/${job.id}`} className="hover:text-slate-800 font-mono">{job.id}</a>
            <span>/</span>
            <span className="text-slate-700 font-medium">Proposal Studio</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 mt-1">{job.title}</h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-slate-400">Target Budget</div>
            <div className="text-sm font-bold text-slate-900">${proposal.proposed_rate.toLocaleString()}</div>
          </div>
          <span
            data-testid="proposal-status-badge"
            className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
              proposal.status === "submitted"
                ? "bg-emerald-100 text-emerald-800"
                : proposal.status === "rejected"
                ? "bg-rose-100 text-rose-800"
                : "bg-blue-100 text-blue-800"
            }`}
          >
            {proposal.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Proposal & Screening */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                Evidence-Grounded Proposal Draft
              </h2>
              <span className="text-[11px] text-slate-500 font-medium">
                Critic Grounding Score: {(proposal.critic_score * 100).toFixed(0)}%
              </span>
            </div>

            <div
              data-testid="proposal-cover-letter-view"
              className="text-xs text-slate-800 leading-relaxed font-sans whitespace-pre-wrap space-y-2 p-4 bg-slate-50/50 rounded-lg border border-slate-100"
            >
              {renderFormattedProposal(proposal.cover_letter)}
            </div>
          </div>

          {proposal.screening_answers.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
              <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
                Client Screening Answers
              </h2>
              <div className="space-y-4">
                {proposal.screening_answers.map((sa, i) => (
                  <div key={i} className="text-xs space-y-1">
                    <p className="font-semibold text-slate-700">Q: {sa.question}</p>
                    <p className="text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100">
                      {sa.answer}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Approval Controls */}
          <ApprovalPanel jobId={job.id} proposal={proposal} onUpdate={setProposal} />
        </div>

        {/* Right: Job Context & Verifier Info */}
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Opportunity Brief</h3>
            <p className="text-xs text-slate-600 line-clamp-4">{job.description}</p>
            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-500">Client Trust Score</span>
              <span className="font-semibold text-emerald-700">{(job.client_trust_score * 100).toFixed(0)}%</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">Fit Match Rating</span>
              <span className="font-semibold text-blue-700">{(job.fit_score * 100).toFixed(0)}%</span>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Audited Evidence Sources</h3>
            <div className="space-y-2">
              {proposal.evidence_items.map((ev) => (
                <div key={ev.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs space-y-1">
                  <div className="font-semibold text-slate-800 truncate">{ev.title}</div>
                  <div className="text-[11px] font-mono text-blue-600 font-medium">[{ev.id}]</div>
                  {ev.metric && <div className="text-[11px] text-emerald-700 font-medium">✓ {ev.metric}</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApprovalDetail, EvidenceItem } from "@/lib/types";
import { api } from "@/lib/client";
import { EvidenceHover } from "@/components/EvidenceHover";
import { ApprovalPanel } from "@/components/ApprovalPanel";

export default function StudioPage() {
  const params = useParams();
  const id = (params?.id as string) || "job_001";

  const [approval, setApproval] = useState<ApprovalDetail | null>(null);
  const [jobInfo, setJobInfo] = useState<{ id: string; title: string; description?: string; connects_cost?: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingRun, setStartingRun] = useState(false);

  useEffect(() => {
    loadApproval();
  }, [id]);

  async function loadApproval() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.approvals.get(id);
      setApproval(data);

      const targetJobId = data.job_id || id;
      try {
        const j = await api.jobs.get(targetJobId);
        setJobInfo({ id: j.id, title: j.title, description: j.description, connects_cost: j.connects_cost });
      } catch {
        setJobInfo({ id: targetJobId, title: data.job_title || `Job ${targetJobId}` });
      }
    } catch (err: any) {
      setError(err.message || "No pending approval dossier found");
    } finally {
      setLoading(false);
    }
  }

  async function handleStartRun() {
    setStartingRun(true);
    try {
      await api.runs.create({ job_id: id });
      // Poll briefly for approval
      setTimeout(() => {
        loadApproval();
        setStartingRun(false);
      }, 3000);
    } catch (err: any) {
      alert(`Failed to start run: ${err.message}`);
      setStartingRun(false);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-400">Loading proposal studio from live API...</div>;
  }

  if (error || !approval) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <div className="p-4 bg-amber-50 border border-amber-200 text-amber-900 rounded-xl text-xs space-y-2">
          <div className="font-semibold text-sm">No Pending Approval for Opportunity: {id}</div>
          <p className="text-amber-800">
            {error || "This opportunity has not produced an approval dossier yet. Start an analysis run to generate an evidence-grounded bid."}
          </p>
          <div className="pt-2 flex items-center gap-3">
            <button
              onClick={handleStartRun}
              disabled={startingRun}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-xs disabled:opacity-50"
            >
              {startingRun ? "Running Bid Pipeline..." : "Generate Proposal (Run Pipeline)"}
            </button>
            <button
              onClick={loadApproval}
              className="px-3 py-2 border border-slate-300 rounded-lg text-xs hover:bg-slate-50 text-slate-700"
            >
              Retry
            </button>
            <a href="/inbox" className="text-xs text-blue-600 hover:text-blue-700">
              ← Return to Inbox
            </a>
          </div>
        </div>
      </div>
    );
  }

  // Render text replacing [E:...] with EvidenceHover interactive pills backed by real evidence
  function renderFormattedProposal(text: string, evidenceStore?: Record<string, EvidenceItem>) {
    if (!text) return null;
    const parts = text.split(/(\[(?:E:)?[a-zA-Z0-9_\-]+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[(?:E:)?([a-zA-Z0-9_\-]+)\]$/);
      if (match) {
        return (
          <EvidenceHover key={idx} evidenceId={match[1]} evidenceStore={evidenceStore}>
            {part}
          </EvidenceHover>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  }

  const jobTitle = jobInfo?.title || approval.job_title || "Proposal Review";
  const coverLetter = approval.draft?.cover_letter || "";
  const screeningAnswers = approval.draft?.screening_answers || [];
  const proposedRate =
    approval.draft?.proposed_rate ||
    approval.price_rationale?.proposed_rate ||
    approval.price_rationale?.bid_amount ||
    0;

  const evidenceItemsList = Object.values(approval.evidence_store || {});
  const status = (approval as any).status || "draft";

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <a href="/inbox" className="hover:text-slate-800">Inbox</a>
            <span>/</span>
            <a href={`/jobs/${jobInfo?.id || id}`} className="hover:text-slate-800 font-mono">
              {jobInfo?.id || id}
            </a>
            <span>/</span>
            <span className="text-slate-700 font-medium">Proposal Studio</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 mt-1">{jobTitle}</h1>
        </div>

        <div className="flex items-center gap-3">
          {proposedRate > 0 && (
            <div className="text-right">
              <div className="text-xs text-slate-400">Target Budget</div>
              <div className="text-sm font-bold text-slate-900">${proposedRate.toLocaleString()}</div>
            </div>
          )}
          <span
            data-testid="proposal-status-badge"
            className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${
              status === "submitted"
                ? "bg-emerald-100 text-emerald-800"
                : status === "rejected"
                ? "bg-rose-100 text-rose-800"
                : "bg-blue-100 text-blue-800"
            }`}
          >
            {status}
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
              {approval.critic_comments?.grounding != null && (
                <span className="text-[11px] text-slate-500 font-medium">
                  Critic Grounding Score: {(approval.critic_comments.grounding * 100).toFixed(0)}%
                </span>
              )}
            </div>

            <div
              data-testid="proposal-cover-letter-view"
              className="text-xs text-slate-800 leading-relaxed font-sans whitespace-pre-wrap space-y-2 p-4 bg-slate-50/50 rounded-lg border border-slate-100"
            >
              {renderFormattedProposal(coverLetter, approval.evidence_store)}
            </div>
          </div>

          {screeningAnswers.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
              <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
                Client Screening Answers
              </h2>
              <div className="space-y-4">
                {screeningAnswers.map((sa, i) => (
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
          <ApprovalPanel
            jobId={id}
            proposal={{
              status,
              cover_letter: coverLetter,
              rejection_reason: (approval as any).rejection_reason,
              compliance_violations: approval.compliance_comments?.violations || [],
            }}
            onUpdate={(updated) => {
              setApproval((prev) =>
                prev
                  ? {
                      ...prev,
                      status: updated.status,
                      rejection_reason: updated.rejection_reason || (prev as any).rejection_reason,
                      draft: { ...prev.draft, cover_letter: updated.cover_letter || prev.draft.cover_letter },
                    }
                  : null
              );
            }}
          />
        </div>

        {/* Right: Job Context & Verifier Info */}
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Opportunity Brief</h3>
            {jobInfo?.description && (
              <p className="text-xs text-slate-600 line-clamp-4">{jobInfo.description}</p>
            )}
            {approval.dry_run?.connects_cost != null && (
              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-500">Connects Cost</span>
                <span className="font-semibold text-slate-800">{approval.dry_run.connects_cost} connects</span>
              </div>
            )}
            {approval.risk?.scam_score != null && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Risk Assessment</span>
                <span className="font-semibold text-slate-800">
                  {approval.risk.is_scam ? "🚨 HIGH RISK" : "✓ Low Risk"}
                </span>
              </div>
            )}
          </div>

          {evidenceItemsList.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
              <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                Audited Evidence Sources ({evidenceItemsList.length})
              </h3>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {evidenceItemsList.map((ev) => (
                  <div key={ev.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs space-y-1">
                    <div className="font-semibold text-slate-800 truncate">{ev.title || ev.project || ev.id}</div>
                    <div className="text-[11px] font-mono text-blue-600 font-medium">[{ev.id}]</div>
                    {ev.metric && <div className="text-[11px] text-emerald-700 font-medium">✓ {ev.metric}</div>}
                    <p className="text-[11px] text-slate-600 line-clamp-2">{ev.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

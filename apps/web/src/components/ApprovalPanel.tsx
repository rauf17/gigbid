"use client";

import React, { useState } from "react";
import { api } from "@/lib/client";

interface ApprovalPanelProps {
  jobId: string;
  proposal: {
    status: string;
    cover_letter: string;
    rejection_reason?: string;
    compliance_violations?: string[];
  };
  onUpdate: (updated: any) => void;
}

export function ApprovalPanel({ jobId, proposal, onUpdate }: ApprovalPanelProps) {
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectBox, setShowRejectBox] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState(proposal.cover_letter);
  const [rejectionReason, setRejectionReason] = useState(proposal.rejection_reason || "");
  const [complianceWarning, setComplianceWarning] = useState<string | null>(
    proposal.compliance_violations && proposal.compliance_violations.length > 0
      ? proposal.compliance_violations[0]
      : null
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dryRun, setDryRun] = useState(true);

  async function handleApprove() {
    setIsSubmitting(true);
    try {
      await api.approvals.decide(jobId, { action: "approve" });
      onUpdate({ ...proposal, status: "submitted" });
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleReject() {
    if (!rejectReason.trim()) return;
    setIsSubmitting(true);
    try {
      await api.approvals.decide(jobId, { action: "reject", reason: rejectReason });
      setRejectionReason(rejectReason);
      onUpdate({ ...proposal, status: "rejected", rejection_reason: rejectReason });
      setShowRejectBox(false);
    } catch (err: any) {
      alert(`Rejection error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSaveEdit() {
    setIsSubmitting(true);
    try {
      const res = await api.approvals.decide(jobId, { action: "edit", edited_text: draftText });
      if ((res.status === "blocked" || res.status === "compliance_violation") && res.violations?.length) {
        setComplianceWarning(res.violations[0]);
      } else {
        setComplianceWarning(null);
        onUpdate({ ...proposal, cover_letter: draftText, status: "awaiting_approval" });
      }
      setIsEditing(false);
    } catch (err: any) {
      alert(`Update error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  const isApproved = proposal.status === "submitted";
  const isRejected = proposal.status === "rejected" || !!rejectionReason;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Review & Approval Control</h3>
          <p className="text-xs text-slate-500">Autonomous bidding guardrail — human review required before dispatch.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-slate-600 flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            Dry Run Mode
          </label>
        </div>
      </div>

      {complianceWarning && (
        <div
          data-testid="compliance-violation-alert"
          className="bg-amber-50 border border-amber-300 text-amber-900 px-4 py-3 rounded-lg text-xs flex items-start gap-3"
        >
          <span className="text-base">⚠️</span>
          <div>
            <span className="font-semibold">Policy Pack Compliance Warning:</span>
            <p className="mt-0.5">{complianceWarning}</p>
          </div>
        </div>
      )}

      {isEditing ? (
        <div className="space-y-3">
          <textarea
            data-testid="proposal-edit-textarea"
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            rows={8}
            className="w-full text-xs font-mono p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => {
                setDraftText(proposal.cover_letter);
                setIsEditing(false);
              }}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              data-testid="save-edit-button"
              onClick={handleSaveEdit}
              disabled={isSubmitting}
              className="px-4 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-sm"
            >
              Save Changes
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-2">
            <button
              data-testid="edit-draft-button"
              onClick={() => setIsEditing(true)}
              disabled={isApproved || isRejected}
              className="px-3 py-2 text-xs font-medium border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              ✏️ Edit Draft
            </button>
            <button
              data-testid="toggle-reject-button"
              onClick={() => setShowRejectBox(!showRejectBox)}
              disabled={isApproved || isRejected}
              className="px-3 py-2 text-xs font-medium border border-rose-200 text-rose-700 rounded-lg hover:bg-rose-50 transition-colors disabled:opacity-50"
            >
              Reject Proposal...
            </button>
          </div>

          <button
            data-testid="approve-proposal-button"
            onClick={handleApprove}
            disabled={isApproved || isRejected || isSubmitting}
            className={`px-5 py-2 text-xs font-semibold rounded-lg shadow-sm transition-all ${
              isApproved
                ? "bg-emerald-600 text-white cursor-default"
                : "bg-emerald-600 hover:bg-emerald-700 text-white active:scale-95"
            } disabled:opacity-50`}
          >
            {isApproved ? "✓ Proposal Approved & Dispatched" : isSubmitting ? "Dispatching..." : "Approve & Submit Bid"}
          </button>
        </div>
      )}

      {showRejectBox && (
        <div data-testid="rejection-box" className="p-4 bg-rose-50/50 border border-rose-200 rounded-lg space-y-3">
          <label className="block text-xs font-medium text-rose-900">
            Specify mandatory rejection feedback for autonomous model learning:
          </label>
          <textarea
            data-testid="rejection-reason-textarea"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="e.g. Rate is too low for this scope / Client project requires on-site presence..."
            rows={2}
            className="w-full text-xs p-2.5 border border-rose-300 rounded-md focus:ring-rose-500 focus:border-rose-500 bg-white"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowRejectBox(false)}
              className="px-3 py-1 text-xs text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              data-testid="confirm-reject-button"
              onClick={handleReject}
              disabled={!rejectReason.trim() || isSubmitting}
              className="px-4 py-1.5 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-md shadow-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              Confirm Rejection
            </button>
          </div>
        </div>
      )}

      {isApproved && (
        <div data-testid="approval-success-badge" className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs font-medium flex items-center gap-2">
          <span>✓</span> Proposal successfully approved and recorded in marketplace submission log.
        </div>
      )}

      {isRejected && (
        <div data-testid="rejection-success-badge" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs font-medium">
          ✗ Proposal was rejected. Reason: &ldquo;{rejectionReason || proposal.rejection_reason}&rdquo;
        </div>
      )}
    </div>
  );
}

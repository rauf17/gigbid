"use client";

import React from "react";

export default function MessagesPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">Client Liaison & Negotiations</h1>
        <p className="text-xs text-slate-500">Autonomous client message management and screening clarifications.</p>
      </div>

      <div
        data-testid="messages-disabled-notice"
        className="bg-amber-50 border border-amber-200 rounded-2xl p-8 text-center space-y-4 shadow-sm"
      >
        <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xl mx-auto">
          ⚠️
        </div>

        <div className="space-y-1">
          <h2 className="text-base font-bold text-amber-900">
            Autonomous Client Liaison Disabled (HTTP 501)
          </h2>
          <p className="text-xs text-amber-800 max-w-md mx-auto">
            Direct outbound client messaging and autonomous contract negotiation are currently restricted by policy in human-supervised mode to prevent unreviewed commitments.
          </p>
        </div>

        <div className="inline-block bg-white border border-amber-200 rounded-lg px-4 py-2 text-xs font-mono text-amber-800">
          Status: 501 Not Implemented — Awaiting Agent Expansion
        </div>
      </div>
    </div>
  );
}

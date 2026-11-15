"use client";

import React from "react";

export interface TimelineStep {
  id: string;
  node: string;
  status: "completed" | "running" | "failed" | "pending";
  latency_ms: number;
  tokens: number;
  summary: string;
  timestamp: string;
}

interface RunTimelineProps {
  runId: string;
  steps: TimelineStep[];
  isStreaming?: boolean;
}

export function RunTimeline({ runId, steps, isStreaming = false }: RunTimelineProps) {
  const nodeIcons: Record<string, string> = {
    analyst: "🔍",
    risk_assessor: "🛡️",
    fit_matcher: "🎯",
    writer: "✍️",
    verifier: "🔬",
    critic: "⚖️",
    compliance: "📜",
    approval_interrupt: "⏸️",
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Autonomous Graph Run Trace</h3>
          <p className="text-xs font-mono text-slate-500">Run ID: {runId}</p>
        </div>
        {isStreaming && (
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-emerald-700">SSE Stream Live</span>
          </div>
        )}
      </div>

      <div className="relative border-l-2 border-slate-200 ml-4 space-y-6">
        {steps.map((step, idx) => {
          const isDone = step.status === "completed";
          const isCurrent = step.status === "running";
          const isFailed = step.status === "failed";

          return (
            <div key={step.id || idx} className="relative pl-6">
              <span
                className={`absolute -left-[17px] top-1 w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs shadow-sm bg-white ${
                  isDone
                    ? "border-emerald-500 text-emerald-600"
                    : isCurrent
                    ? "border-blue-500 text-blue-600 animate-bounce"
                    : isFailed
                    ? "border-rose-500 text-rose-600"
                    : "border-slate-300 text-slate-400"
                }`}
              >
                {nodeIcons[step.node] || "⚙️"}
              </span>

              <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 hover:bg-slate-100/70 transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-800 capitalize">
                    {step.node.replace("_", " ")}
                  </span>
                  <div className="flex items-center gap-3 text-[11px] font-mono text-slate-500">
                    <span>{step.latency_ms}ms</span>
                    <span>{step.tokens} tokens</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
                        isDone
                          ? "bg-emerald-100 text-emerald-800"
                          : isCurrent
                          ? "bg-blue-100 text-blue-800"
                          : isFailed
                          ? "bg-rose-100 text-rose-800"
                          : "bg-slate-200 text-slate-600"
                      }`}
                    >
                      {step.status}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-600 mt-1">{step.summary}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

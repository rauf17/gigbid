"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RunTimeline, TimelineStep } from "@/components/RunTimeline";
import { api } from "@/lib/client";

export default function RunTracePage() {
  const params = useParams();
  const runId = (params?.id as string) || "run_001";
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [isStreaming, setIsStreaming] = useState(true);
  const [runStatus, setRunStatus] = useState<string>("running");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 1. Load initial trace history from backend
    api.runs.trace(runId)
      .then((res) => {
        if (res.traces && res.traces.length > 0) {
          const loaded: TimelineStep[] = res.traces.map((t, idx) => ({
            id: t.id ? String(t.id) : `step_${idx}`,
            node: t.node_name,
            status: "completed",
            latency_ms: Math.round(t.duration_ms || 0),
            tokens: t.tokens || 0,
            summary: t.observation || `Completed ${t.node_name}`,
            timestamp: t.created_at || new Date().toISOString(),
          }));
          setSteps(loaded);
        }
      })
      .catch((err) => {
        // If trace fails, log warning
        console.warn("Could not load initial run trace:", err);
      });

    // 2. Connect to SSE stream
    let es: EventSource | null = null;
    try {
      es = new EventSource(`/api/runs/${runId}/stream`);

      es.addEventListener("node_update", (event) => {
        try {
          const data = JSON.parse(event.data);
          const nodeName = data.node || "node";
          const updates = data.updates || {};

          setSteps((prev) => {
            const nextStep: TimelineStep = {
              id: `step_${prev.length + 1}`,
              node: nodeName,
              status: updates.status === "failed" ? "failed" : "completed",
              latency_ms: updates.latency_ms || 0,
              tokens: updates.tokens || 0,
              summary: updates.summary || `Node ${nodeName} execution completed.`,
              timestamp: new Date().toISOString(),
            };
            return [...prev, nextStep];
          });

          if (updates.status) {
            setRunStatus(updates.status);
          }
        } catch {
          // ignore parsing error
        }
      });

      es.addEventListener("final", (event) => {
        try {
          const data = JSON.parse(event.data);
          setRunStatus(data.status || "stream_completed");
        } catch {}
        setIsStreaming(false);
        es?.close();
      });

      es.onerror = () => {
        setIsStreaming(false);
        es?.close();
      };
    } catch (err: any) {
      setError(err.message || "Failed connecting to SSE stream");
      setIsStreaming(false);
    }

    return () => {
      es?.close();
    };
  }, [runId]);

  const jobId = runId.includes(":") ? runId.split(":")[1] : runId;
  const isAwaitingApproval = runStatus === "awaiting_approval" || steps.some((s) => s.node === "approval_interrupt" || s.node === "approval");

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <a href="/inbox" className="hover:text-slate-800">← Back to Inbox</a>
            <span>/</span>
            <span className="font-mono">{runId}</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 mt-1">Live Execution Trace</h1>
        </div>

        <div className="flex items-center gap-2">
          {isAwaitingApproval && (
            <a
              href={`/studio/${jobId}`}
              className="px-4 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all"
            >
              Open in Proposal Studio →
            </a>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
          <span className="font-semibold">Stream connection error:</span> {error}
        </div>
      )}

      {steps.length === 0 && !error ? (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-xs text-slate-400">
          Listening for graph state transitions on thread <span className="font-mono">{runId}</span>...
        </div>
      ) : (
        <RunTimeline runId={runId} steps={steps} isStreaming={isStreaming} />
      )}
    </div>
  );
}

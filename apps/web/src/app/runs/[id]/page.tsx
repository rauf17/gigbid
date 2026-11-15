"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RunTimeline, TimelineStep } from "@/components/RunTimeline";

const INITIAL_STEPS: TimelineStep[] = [
  {
    id: "step_01",
    node: "analyst",
    status: "completed",
    latency_ms: 1240,
    tokens: 420,
    summary: "Extracted 3 atomic requirements and identified skill requirements [Python, LightGBM].",
    timestamp: new Date(Date.now() - 10000).toISOString(),
  },
  {
    id: "step_02",
    node: "risk_assessor",
    status: "completed",
    latency_ms: 890,
    tokens: 310,
    summary: "Evaluated client trust (0.96) and scam probability (0.02). Risk classification: LOW.",
    timestamp: new Date(Date.now() - 8000).toISOString(),
  },
  {
    id: "step_03",
    node: "fit_matcher",
    status: "completed",
    latency_ms: 640,
    tokens: 280,
    summary: "Calibrated similarity score: 0.94. Strong portfolio grounding chunk cs_aiml_001.",
    timestamp: new Date(Date.now() - 6000).toISOString(),
  },
  {
    id: "step_04",
    node: "writer",
    status: "completed",
    latency_ms: 2450,
    tokens: 780,
    summary: "Drafted tailored proposal cover letter with inline evidence markers [E:ai_ml_cs_cs_aiml_001].",
    timestamp: new Date(Date.now() - 3000).toISOString(),
  },
  {
    id: "step_05",
    node: "verifier",
    status: "completed",
    latency_ms: 1100,
    tokens: 520,
    summary: "Audited 5 atomic claims against portfolio. 0 unsupported assertions detected.",
    timestamp: new Date(Date.now() - 1500).toISOString(),
  },
  {
    id: "step_06",
    node: "critic",
    status: "completed",
    latency_ms: 920,
    tokens: 390,
    summary: "Evaluated grounding (0.92) and personalization (0.88). Verdict: ACCEPT.",
    timestamp: new Date(Date.now() - 800).toISOString(),
  },
  {
    id: "step_07",
    node: "approval_interrupt",
    status: "running",
    latency_ms: 0,
    tokens: 0,
    summary: "LangGraph approval interrupt triggered. Awaiting human approval command.",
    timestamp: new Date().toISOString(),
  },
];

export default function RunTracePage() {
  const params = useParams();
  const runId = (params?.id as string) || "run_demo_001";
  const [steps, setSteps] = useState<TimelineStep[]>(INITIAL_STEPS);
  const [isStreaming, setIsStreaming] = useState(true);

  useEffect(() => {
    // Attempt SSE connection if backend is available
    if (typeof EventSource !== "undefined") {
      try {
        const es = new EventSource(`/api/runs/${runId}/events`);
        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data?.node) {
              setSteps((prev) => [...prev, data]);
            }
          } catch {
            // ignore parse errors
          }
        };
        es.onerror = () => {
          es.close();
          setIsStreaming(false);
        };
        return () => es.close();
      } catch {
        setIsStreaming(false);
      }
    }
  }, [runId]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">Execution Trace & State Inspector</h1>
        <p className="text-xs text-slate-500">
          Step-by-step audit of LangGraph state transitions, LLM tokens, and node execution latencies.
        </p>
      </div>

      <RunTimeline runId={runId} steps={steps} isStreaming={isStreaming} />
    </div>
  );
}

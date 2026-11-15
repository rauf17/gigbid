"use client";

import React, { useEffect, useState } from "react";
import { ProposalItem, ProposalPipeline } from "@/lib/types";
import { api } from "@/lib/client";

const STAGES: Array<{ id: keyof ProposalPipeline; label: string }> = [
  { id: "drafted", label: "Drafted" },
  { id: "submitted", label: "Submitted" },
  { id: "viewed", label: "Viewed" },
  { id: "replied", label: "Replied" },
  { id: "interview", label: "Interview" },
  { id: "hired", label: "Hired" },
  { id: "lost", label: "Lost" },
];

export default function PipelinePage() {
  const [pipeline, setPipeline] = useState<ProposalPipeline>({
    drafted: [],
    submitted: [],
    viewed: [],
    replied: [],
    interview: [],
    hired: [],
    lost: [],
  });
  const [tickCount, setTickCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [ticking, setTicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPipeline();
  }, []);

  async function loadPipeline() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.proposals.pipeline();
      setPipeline(data);
    } catch (err: any) {
      setError(err.message || "Failed loading proposal pipeline");
    } finally {
      setLoading(false);
    }
  }

  async function handleTick() {
    setTicking(true);
    try {
      const res = await api.sim.tick();
      setTickCount(res.tick);
      await loadPipeline();
    } catch (err: any) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setTicking(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Bidding Pipeline Kanban</h1>
          <p className="text-xs text-slate-500">Autonomous progression of job opportunities across bidding lifecycle.</p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500">Sim Ticks: {tickCount}</span>
          <button
            data-testid="sim-tick-button"
            onClick={handleTick}
            disabled={ticking}
            className="px-4 py-2 text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white rounded-lg shadow-sm transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            <span>⏩</span>
            <span>{ticking ? "Advancing..." : "Advance Simulation (Tick)"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between">
          <div><span className="font-semibold">Error:</span> {error}</div>
          <button onClick={loadPipeline} className="px-3 py-1 bg-rose-600 text-white rounded-lg text-xs">Retry</button>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-400">Loading live proposal pipeline...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-3 overflow-x-auto min-h-[500px]">
          {STAGES.map((stage) => {
            const stageItems: ProposalItem[] = pipeline[stage.id] || [];
            return (
              <div
                key={stage.id}
                data-testid={`kanban-column-${stage.id}`}
                className="bg-slate-100/70 rounded-xl p-3 flex flex-col min-w-[200px]"
              >
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200">
                  <span className="text-xs font-semibold text-slate-700">{stage.label}</span>
                  <span className="text-[10px] font-bold bg-white text-slate-600 px-1.5 py-0.5 rounded-full border border-slate-200">
                    {stageItems.length}
                  </span>
                </div>

                <div className="space-y-2 flex-1">
                  {stageItems.length === 0 ? (
                    <div className="text-[11px] text-slate-400 text-center py-6">Empty</div>
                  ) : (
                    stageItems.map((prop, idx) => {
                      const cleanJobId = prop.job_id || prop.thread_id.split(":")[1] || prop.thread_id;
                      return (
                        <div
                          key={prop.thread_id || idx}
                          className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs hover:shadow-sm transition-shadow text-xs space-y-2"
                        >
                          <a
                            href={`/studio/${cleanJobId}`}
                            className="font-semibold text-slate-800 hover:text-blue-600 line-clamp-2 block"
                          >
                            {cleanJobId}
                          </a>
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span>Persona: {prop.persona_id}</span>
                            {prop.bid_amount != null && (
                              <span className="text-emerald-700 font-semibold font-mono">
                                ${prop.bid_amount.toLocaleString()}
                              </span>
                            )}
                          </div>
                          {prop.created_at && (
                            <div className="text-[10px] text-slate-400">
                              {new Date(prop.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

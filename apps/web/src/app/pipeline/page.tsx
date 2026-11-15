"use client";

import React, { useEffect, useState } from "react";
import { MockJob } from "@/lib/mock_data";
import { api } from "@/lib/client";

const STAGES = [
  { id: "discovered", label: "Discovered" },
  { id: "analyzing", label: "Analyzing" },
  { id: "drafting", label: "Drafting" },
  { id: "awaiting_review", label: "Awaiting Review" },
  { id: "submitted", label: "Submitted" },
  { id: "won", label: "Won" },
  { id: "lost", label: "Lost" },
];

export default function PipelinePage() {
  const [jobs, setJobs] = useState<MockJob[]>([]);
  const [tickCount, setTickCount] = useState(0);
  const [ticking, setTicking] = useState(false);

  useEffect(() => {
    api.jobs.list().then((res) => setJobs(res));
  }, []);

  async function handleTick() {
    setTicking(true);
    try {
      const res = await api.sim.tick();
      setTickCount(res.tick);
      // Refresh jobs
      const updated = await api.jobs.list();
      setJobs(updated);
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

      <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-3 overflow-x-auto min-h-[500px]">
        {STAGES.map((stage) => {
          const stageJobs = jobs.filter((j) => j.status === stage.id);
          return (
            <div
              key={stage.id}
              data-testid={`kanban-column-${stage.id}`}
              className="bg-slate-100/70 rounded-xl p-3 flex flex-col min-w-[200px]"
            >
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200">
                <span className="text-xs font-semibold text-slate-700">{stage.label}</span>
                <span className="text-[10px] font-bold bg-white text-slate-600 px-1.5 py-0.5 rounded-full border border-slate-200">
                  {stageJobs.length}
                </span>
              </div>

              <div className="space-y-2 flex-1">
                {stageJobs.map((job) => (
                  <div
                    key={job.id}
                    className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs hover:shadow-sm transition-shadow text-xs space-y-2"
                  >
                    <a
                      href={`/studio/${job.id}`}
                      className="font-semibold text-slate-800 hover:text-blue-600 line-clamp-2 block"
                    >
                      {job.title}
                    </a>
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>${job.budget_max.toLocaleString()}</span>
                      <span className="text-emerald-700 font-medium font-mono">
                        {(job.fit_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

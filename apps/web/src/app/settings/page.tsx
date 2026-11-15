"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/client";

export default function SettingsPage() {
  const [profile, setProfile] = useState<{
    autonomy_mode?: string;
    budget_cap?: number;
    saved_searches?: string[];
  }>({
    autonomy_mode: "supervised",
    budget_cap: 10000,
    saved_searches: ["LangGraph", "FastAPI", "LightGBM", "DuckDB"],
  });

  const [memories, setMemories] = useState<Array<{ id: string; key: string; value: string }>>([]);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    Promise.all([api.profile.get(), api.memory.list()])
      .then(([p, m]: [any, any]) => {
        if (p) setProfile(p);
        if (m) {
          const rawItems = Array.isArray(m) ? m : m.items || [];
          const normalized = rawItems.map((it: any, idx: number) => ({
            id: it.id || it.key || `mem_${idx}`,
            key: it.key,
            value: typeof it.value === "object" ? JSON.stringify(it.value) : String(it.value),
          }));
          setMemories(normalized);
        }
      })
      .catch((err) => {
        console.warn("Failed loading profile or memories:", err);
      });
  }, []);

  async function handleSave() {
    await api.profile.update(profile);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  }

  async function handleClearMemories() {
    if (confirm("Are you sure you want to clear long-term memories?")) {
      await api.memory.clear();
      setMemories([]);
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">Platform Settings & Memory</h1>
        <p className="text-xs text-slate-500">Autonomous bidding policies, spending limits, and long-term memory store.</p>
      </div>

      {savedSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg font-medium">
          ✓ Configuration settings saved successfully.
        </div>
      )}

      {/* Autonomy Mode */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">Autonomous Bidding Level</h2>
          <p className="text-xs text-slate-500 mt-0.5">Control the level of human supervision before bid submission.</p>
        </div>

        <div className="space-y-2">
          {[
            {
              id: "supervised",
              title: "Human-in-the-Loop Supervised (Default)",
              desc: "Graph pauses at approval interrupt. Every proposal must be explicitly reviewed in Studio.",
            },
            {
              id: "semi_autonomous",
              title: "Semi-Autonomous with Budget Threshold",
              desc: "Auto-submits proposals below $1,000 where match score > 90%; holds larger opportunities for review.",
            },
            {
              id: "autonomous",
              title: "Fully Autonomous (High Trust)",
              desc: "Dispatches all compliant bids automatically. Nightly summaries sent to dashboard.",
            },
          ].map((mode) => (
            <label
              key={mode.id}
              className={`flex items-start gap-3 p-3.5 border rounded-lg cursor-pointer transition-all ${
                profile.autonomy_mode === mode.id
                  ? "border-blue-600 bg-blue-50/40"
                  : "border-slate-200 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="autonomy_mode"
                value={mode.id}
                checked={profile.autonomy_mode === mode.id}
                onChange={() => setProfile({ ...profile, autonomy_mode: mode.id })}
                className="mt-0.5 text-blue-600 focus:ring-blue-500"
              />
              <div className="space-y-0.5">
                <span className="text-xs font-semibold text-slate-800 block">{mode.title}</span>
                <span className="text-xs text-slate-500 block">{mode.desc}</span>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Budget & Saved Searches */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
        <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
          Weekly Spending Caps & Search Queries
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Weekly Proposal Cap (USD)
            </label>
            <input
              type="number"
              value={profile.budget_cap || 10000}
              onChange={(e) => setProfile({ ...profile, budget_cap: Number(e.target.value) })}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Saved Marketplace Search Terms (comma-separated)
            </label>
            <input
              type="text"
              value={(profile.saved_searches || []).join(", ")}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  saved_searches: e.target.value.split(",").map((s) => s.trim()),
                })
              }
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleSave}
            className="px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all"
          >
            Save Preferences
          </button>
        </div>
      </div>

      {/* Long-Term Memory Store */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
              Postgres Long-Term Memory Store
            </h2>
            <p className="text-xs text-slate-500">Autonomous agent cross-run learnings and client pricing memory.</p>
          </div>
          <button
            onClick={handleClearMemories}
            disabled={memories.length === 0}
            className="px-3 py-1.5 text-xs font-medium border border-rose-200 text-rose-700 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-40"
          >
            Clear Memories
          </button>
        </div>

        {memories.length === 0 ? (
          <div className="text-xs text-slate-400 py-4 text-center">Memory store is currently empty.</div>
        ) : (
          <div className="space-y-2">
            {memories.map((m) => (
              <div key={m.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs flex justify-between gap-4">
                <span className="font-mono text-blue-700 font-medium shrink-0">{m.key}</span>
                <span className="text-slate-600 text-right">{m.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import { AnalyticsResponse } from "@/lib/types";
import { api } from "@/lib/client";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAnalytics();
  }, []);

  async function loadAnalytics() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.analytics.get();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed loading performance analytics");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-400">Loading performance analytics from database...</div>;
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between">
          <div><span className="font-semibold">Error loading analytics:</span> {error || "No data returned"}</div>
          <button onClick={loadAnalytics} className="px-3 py-1 bg-rose-600 text-white rounded-lg text-xs">Retry</button>
        </div>
      </div>
    );
  }

  const outcomes = data.outcomes_by_category || [];
  const connects = data.connects_spent_vs_outcomes || [];
  const costs = data.cost_and_latency || [];
  const rejections = data.top_rejection_reasons || [];

  const totalBids = outcomes.reduce((acc, c) => acc + c.bids, 0);
  const totalHires = outcomes.reduce((acc, c) => acc + c.hires, 0);
  const totalReplies = outcomes.reduce((acc, c) => acc + c.replies, 0);
  const totalSpendUSD = costs.reduce((acc, c) => acc + (c.total_cost_usd || 0), 0);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">Performance Analytics</h1>
        <p className="text-xs text-slate-500">
          Autonomous bidding outcomes, win conversion, and rejection attribution computed live from PostgreSQL.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-1">
          <span className="text-xs font-medium text-slate-500">Proposals Logged</span>
          <div className="text-2xl font-bold text-slate-900">{totalBids}</div>
          <span className="text-[11px] font-medium text-blue-600">Total Graph Runs</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-1">
          <span className="text-xs font-medium text-slate-500">Replies Received</span>
          <div className="text-2xl font-bold text-slate-900">{totalReplies}</div>
          <span className="text-[11px] font-medium text-emerald-600">
            {totalBids > 0 ? `${((totalReplies / totalBids) * 100).toFixed(1)}% reply rate` : "No submissions"}
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-1">
          <span className="text-xs font-medium text-slate-500">Hires Won</span>
          <div className="text-2xl font-bold text-slate-900">{totalHires}</div>
          <span className="text-[11px] font-medium text-emerald-600">
            {totalBids > 0 ? `${((totalHires / totalBids) * 100).toFixed(1)}% win rate` : "No hires"}
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-1">
          <span className="text-xs font-medium text-slate-500">LLM Inference Cost</span>
          <div className="text-2xl font-bold text-slate-900">${totalSpendUSD.toFixed(4)}</div>
          <span className="text-[11px] font-medium text-slate-400">Total API spend</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Outcomes */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
            Category Win Rates (Database Aggregation)
          </h2>

          {outcomes.length === 0 ? (
            <div className="text-xs text-slate-400 py-6 text-center">No category runs logged yet.</div>
          ) : (
            <div className="space-y-4 pt-2">
              {outcomes.map((cat) => {
                const winPct = cat.bids > 0 ? (cat.hires / cat.bids) * 100 : 0;
                return (
                  <div key={cat.category} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700 uppercase font-mono">{cat.category}</span>
                      <span className="font-semibold text-slate-900">
                        {cat.hires} won / {cat.bids} bids ({winPct.toFixed(0)}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
                      <div
                        className="bg-blue-600 h-full rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(5, winPct))}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Rejection Reasons Attribution */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
            Human Rejection Feedback Breakdown
          </h2>

          {rejections.length === 0 ? (
            <div className="text-xs text-slate-400 py-6 text-center">No rejections recorded yet.</div>
          ) : (
            <div className="space-y-4 pt-2">
              {rejections.map((r, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-700 truncate">{r.reason}</span>
                    <span className="font-semibold text-slate-900 shrink-0">
                      {r.count} {r.pct != null ? `(${r.pct}%)` : ""}
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
                    <div
                      className="bg-rose-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(5, r.pct ?? 20))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* LLM Model Accounting */}
      {costs.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
            LLM Model Accounting & Latency
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 font-medium">Calls</th>
                  <th className="pb-2 font-medium">Tokens</th>
                  <th className="pb-2 font-medium">Total Cost ($)</th>
                  <th className="pb-2 font-medium">Avg Latency (ms)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {costs.map((c, i) => (
                  <tr key={i} className="py-2">
                    <td className="py-2.5 font-mono text-slate-800">{c.model}</td>
                    <td className="py-2.5 text-slate-700">{c.total_calls}</td>
                    <td className="py-2.5 text-slate-700">{c.total_tokens?.toLocaleString()}</td>
                    <td className="py-2.5 text-slate-700">${c.total_cost_usd?.toFixed(4)}</td>
                    <td className="py-2.5 text-slate-700">{c.avg_latency_ms?.toFixed(1)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

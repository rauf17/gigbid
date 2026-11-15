"use client";

import React from "react";

export default function AnalyticsPage() {
  const metrics = [
    { label: "Proposals Submitted", value: "48", change: "+12% this week" },
    { label: "Interview Conversion", value: "31.2%", change: "+4.5% vs baseline" },
    { label: "Win Rate", value: "22.9%", change: "+3.1% vs baseline" },
    { label: "Total Revenue Won", value: "$38,400", change: "$800/bid avg" },
  ];

  const categoryOutcomes = [
    { category: "AI & Machine Learning", submitted: 24, won: 6, winRate: 25 },
    { category: "Full-Stack Web Dev", submitted: 16, won: 3, winRate: 18.75 },
    { category: "Data Analytics & SQL", submitted: 8, won: 2, winRate: 25 },
  ];

  const rejectionReasons = [
    { reason: "Budget mismatch / rate anchor low", count: 8, pct: 44 },
    { reason: "Client requested in-person presence", count: 5, pct: 28 },
    { reason: "Uncertain requirements scope", count: 3, pct: 17 },
    { reason: "Other / timeline clash", count: 2, pct: 11 },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900">Performance Analytics</h1>
        <p className="text-xs text-slate-500">Autonomous bidding outcomes, win conversion, and rejection attribution.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-1">
            <span className="text-xs font-medium text-slate-500">{m.label}</span>
            <div className="text-2xl font-bold text-slate-900">{m.value}</div>
            <span className="text-[11px] font-medium text-emerald-600">{m.change}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Outcomes */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
            Category Win Rates (CSS Bar Visualization)
          </h2>

          <div className="space-y-4 pt-2">
            {categoryOutcomes.map((cat) => (
              <div key={cat.category} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-700">{cat.category}</span>
                  <span className="font-semibold text-slate-900">{cat.won} won / {cat.submitted} submitted ({cat.winRate}%)</span>
                </div>
                <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
                  <div
                    className="bg-blue-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${cat.winRate * 2.5}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Rejection Reasons Attribution */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-xs font-semibold text-slate-800 uppercase tracking-wider border-b border-slate-100 pb-3">
            Human Rejection Feedback Breakdown
          </h2>

          <div className="space-y-4 pt-2">
            {rejectionReasons.map((r) => (
              <div key={r.reason} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-700 truncate">{r.reason}</span>
                  <span className="font-semibold text-slate-900 shrink-0">{r.count} ({r.pct}%)</span>
                </div>
                <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
                  <div
                    className="bg-rose-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${r.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

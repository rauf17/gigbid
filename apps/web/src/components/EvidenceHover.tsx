"use client";

import React, { useState } from "react";
import { MockEvidenceItem, MOCK_EVIDENCE } from "@/lib/mock_data";

interface EvidenceHoverProps {
  evidenceId: string;
  children: React.ReactNode;
}

export function EvidenceHover({ evidenceId, children }: EvidenceHoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const cleanId = evidenceId.replace(/^\[(?:E:)?/, "").replace(/\]$/, "").trim();
  const evidence: MockEvidenceItem | undefined =
    MOCK_EVIDENCE[cleanId] ||
    Object.values(MOCK_EVIDENCE).find((e) => e.id.includes(cleanId) || cleanId.includes(e.id));

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <span className="cursor-help font-mono text-xs font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 hover:bg-blue-100 transition-colors">
        {children}
      </span>

      {isOpen && evidence && (
        <div
          data-testid="evidence-hover-card"
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 p-3 bg-white border border-slate-200 rounded-lg shadow-xl text-left text-xs pointer-events-none transition-opacity"
        >
          <div className="flex items-center justify-between pb-1 border-b border-slate-100 mb-2">
            <span className="font-semibold text-slate-800 truncate">{evidence.title}</span>
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-mono font-medium">
              Match: {(evidence.score * 100).toFixed(0)}%
            </span>
          </div>

          <p className="text-slate-600 mb-2 line-clamp-3">{evidence.text}</p>

          {evidence.metric && (
            <div className="bg-slate-50 p-1.5 rounded text-slate-700 font-medium text-[11px] mb-2 border border-slate-100">
              📊 <span className="text-slate-900">{evidence.metric}</span>
            </div>
          )}

          <div className="flex flex-wrap gap-1">
            {evidence.skills.map((skill) => (
              <span
                key={skill}
                className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px]"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </span>
  );
}

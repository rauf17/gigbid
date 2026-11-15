"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/client";

export function DegradedBanner() {
  const [isDegraded, setIsDegraded] = useState(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    // Check query param for easy testing in playwright e2e
    if (searchParams.get("degraded") === "1" || searchParams.get("degraded") === "true") {
      setIsDegraded(true);
      return;
    }

    // Health check endpoint probe
    api.health.check().then((status) => {
      if (status.degraded) {
        setIsDegraded(true);
      }
    });
  }, [searchParams]);

  if (!isDegraded) return null;

  return (
    <div
      data-testid="degraded-mode-banner"
      className="bg-amber-600 text-white px-4 py-2.5 text-xs font-medium text-center flex items-center justify-center gap-2 shadow-md sticky top-0 z-50 animate-fadeIn"
    >
      <span className="text-base">⚠️</span>
      <span>
        System Degraded Mode Active (HTTP 503): Primary LLM routing fallen back to lightweight offline heuristics. Active bidding queue throttled.
      </span>
      <button
        onClick={() => setIsDegraded(false)}
        className="ml-4 bg-amber-700/60 hover:bg-amber-800 text-white px-2 py-0.5 rounded text-[11px]"
      >
        Dismiss
      </button>
    </div>
  );
}

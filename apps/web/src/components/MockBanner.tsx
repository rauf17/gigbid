"use client";

import React, { useEffect, useState } from "react";
import { isMockMode } from "@/lib/client";

export function MockBanner() {
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    setIsMock(isMockMode());
  }, []);

  if (!isMock) {
    return null;
  }

  return (
    <div
      data-testid="mock-mode-banner"
      className="bg-amber-500 text-amber-950 px-4 py-2 text-xs font-semibold text-center sticky top-0 z-50 shadow-sm border-b border-amber-600 flex items-center justify-center gap-2"
    >
      <span>⚠️</span>
      <span>DEMO DATA - MOCK MODE ACTIVE (set NEXT_PUBLIC_MOCK=0 or start the backend to use live data)</span>
    </div>
  );
}

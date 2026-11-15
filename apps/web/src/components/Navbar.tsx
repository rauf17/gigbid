"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/client";

export function Navbar() {
  const pathname = usePathname();
  const [profile, setProfile] = useState<{ email?: string; persona_id?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.auth.me()
      .then((data) => {
        if (data?.email) setProfile(data);
      })
      .catch(() => {
        setProfile(null);
      })
      .finally(() => setLoading(false));
  }, [pathname]);

  if (pathname === "/login" || pathname === "/onboarding") {
    return null;
  }

  const navItems = [
    { label: "Inbox", href: "/inbox" },
    { label: "Studio", href: "/studio/job_001" },
    { label: "Pipeline", href: "/pipeline" },
    { label: "Messages", href: "/messages" },
    { label: "Analytics", href: "/analytics" },
    { label: "Settings", href: "/settings" },
  ];

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-6">
            <a href="/inbox" className="flex items-center gap-2">
              <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                GigBid
              </span>
              <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-semibold">
                Autonomous Copilot
              </span>
            </a>

            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-slate-100 text-blue-700 font-semibold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    }`}
                  >
                    {item.label}
                  </a>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {profile?.email ? (
              <>
                <a
                  href="/onboarding"
                  data-testid="navbar-persona-badge"
                  className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 px-2.5 py-1 rounded-full border border-blue-200 font-medium transition-colors"
                >
                  Persona: <span className="font-semibold uppercase">{profile.persona_id || "ai_ml"}</span>
                </a>
                <span data-testid="navbar-user-email" className="text-xs text-slate-700 font-medium hidden sm:inline">
                  {profile.email}
                </span>
                <button
                  data-testid="navbar-logout-btn"
                  onClick={async () => {
                    await api.auth.logout();
                    window.location.href = "/login";
                  }}
                  className="text-[11px] text-slate-500 hover:text-slate-800 transition-colors"
                >
                  Sign Out
                </button>
              </>
            ) : !loading ? (
              <a href="/login" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
                Sign In
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

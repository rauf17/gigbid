import "./globals.css";
import React, { Suspense } from "react";
import { cookies } from "next/headers";
import { Navbar } from "@/components/Navbar";
import { DegradedBanner } from "@/components/DegradedBanner";
import { MockBanner } from "@/components/MockBanner";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "GigBid — Autonomous Bidding Copilot",
  description: "Evidence-grounded autonomous freelancer copilot with human-in-the-loop review",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let isMock = process.env["NEXT_PUBLIC_MOCK"] === "1" || process.env["MOCK"] === "1";
  try {
    const cookieStore = cookies();
    if (cookieStore.get("NEXT_PUBLIC_MOCK")?.value === "1") {
      isMock = true;
    }
  } catch {
    // ignore
  }

  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased">
        <script
          id="mock-detection-script"
          dangerouslySetInnerHTML={{
            __html: `window.__NEXT_PUBLIC_MOCK__ = ${isMock ? "true" : "false"}; document.cookie = "NEXT_PUBLIC_MOCK=${isMock ? "1" : "0"}; path=/";`,
          }}
        />
        <MockBanner />
        <Suspense fallback={null}>
          <DegradedBanner />
        </Suspense>
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}

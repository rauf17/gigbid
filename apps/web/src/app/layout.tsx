import "./globals.css";
import React, { Suspense } from "react";
import { Navbar } from "@/components/Navbar";
import { DegradedBanner } from "@/components/DegradedBanner";

export const metadata = {
  title: "GigBid — Autonomous Bidding Copilot",
  description: "Evidence-grounded autonomous freelancer copilot with human-in-the-loop review",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased">
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

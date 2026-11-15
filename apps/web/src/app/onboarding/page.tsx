"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/client";

interface PersonaOption {
  id: string;
  name: string;
  title: string;
  skills: string[];
  description: string;
}

const PERSONAS: PersonaOption[] = [
  {
    id: "ai_ml",
    name: "AI & Machine Learning Engineer",
    title: "Senior AI/ML Practitioner",
    skills: ["Python", "LightGBM", "PyTorch", "FastAPI", "Docker", "pgvector"],
    description: "Specialized in time-series forecasting, retrieval-augmented generation (RAG), and high-throughput model inferencing.",
  },
  {
    id: "fullstack",
    name: "Full-Stack Web Engineer",
    title: "Senior Full-Stack Developer",
    skills: ["Next.js", "TypeScript", "Tailwind CSS", "FastAPI", "PostgreSQL", "SSE"],
    description: "Specialized in responsive web applications, streaming interfaces, and robust multi-tenant backend architectures.",
  },
  {
    id: "data_analyst",
    name: "Data Analyst & Analytics Engineer",
    title: "Senior Analytics Engineer",
    skills: ["SQL", "DuckDB", "Pandas", "Streamlit", "ETL Pipelines", "dbt"],
    description: "Specialized in automated reconciliation pipelines, executive metric dashboards, and high-performance SQL analytics.",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [selectedPersona, setSelectedPersona] = useState("ai_ml");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSelect(id: string) {
    setSelectedPersona(id);
  }

  async function handleSave() {
    setIsSubmitting(true);
    try {
      await api.profile.update({ persona_id: selectedPersona });
      router.push("/inbox");
    } catch (err: any) {
      alert(`Failed to save persona: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Select Your Freelance Persona</h1>
        <p className="text-xs text-slate-500 max-w-lg mx-auto">
          GigBid anchors proposal claims, retrieval grounding, and fit-scoring against your verified persona portfolio corpus.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PERSONAS.map((p) => {
          const isSelected = selectedPersona === p.id;
          return (
            <div
              key={p.id}
              data-testid={`persona-card-${p.id}`}
              onClick={() => handleSelect(p.id)}
              className={`border-2 rounded-xl p-5 cursor-pointer transition-all flex flex-col justify-between ${
                isSelected
                  ? "border-blue-600 bg-blue-50/50 shadow-md ring-2 ring-blue-500/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm"
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase font-bold text-slate-500">{p.id}</span>
                  {isSelected && (
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px] font-bold">
                      ✓
                    </span>
                  )}
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{p.name}</h3>
                  <p className="text-xs text-slate-500 mt-1">{p.description}</p>
                </div>

                <div className="flex flex-wrap gap-1 pt-2">
                  {p.skills.map((s) => (
                    <span
                      key={s}
                      className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-mono"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="text-slate-400">Portfolio Corpus</span>
                <span className="font-semibold text-slate-700">Verified</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-center pt-4">
        <button
          data-testid="onboarding-continue-button"
          onClick={handleSave}
          disabled={isSubmitting}
          className="px-8 py-2.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-all disabled:opacity-50"
        >
          {isSubmitting ? "Setting Up Persona..." : "Continue to Inbox →"}
        </button>
      </div>
    </div>
  );
}
